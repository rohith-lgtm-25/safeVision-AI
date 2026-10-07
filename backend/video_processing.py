"""
video_processing.py
-------------------
Background video processing for SafeVision AI.

Uses the PPE-only model singleton (best.pt, 4 classes: helmet/no_helmet/mask/no_mask).
Runs each job in a daemon thread to avoid blocking FastAPI.
"""

import os
import uuid
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import cv2

from vision.model import ppe_vision_model
from vision.draw import draw_annotations

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
MAX_VIDEO_BYTES: int = 100 * 1024 * 1024          # 100 MB upload limit
ALLOWED_MIME_TYPES: set = {
    "video/mp4",
    "video/quicktime",   # .mov
    "video/x-msvideo",  # .avi
}
ALLOWED_EXTENSIONS: set = {".mp4", ".mov", ".avi"}

# Process every Nth frame. Increase for speed, decrease for accuracy.
FRAME_INTERVAL: int = int(os.getenv("SAFEVISION_FRAME_INTERVAL", "5"))

# Directory for temporary upload/output files (relative to working directory)
TEMP_DIR: Path = Path("data/temp")

# ── Job Registry ─────────────────────────────────────────────────────────────
# Maps job_id -> job-state dict.  Simple in-memory store (fine for hackathon).
_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _make_job(job_id: str, input_path: Path, output_path: Path) -> Dict[str, Any]:
    return {
        "job_id":      job_id,
        "status":      "queued",   # queued | processing | completed | failed
        "progress":    0,          # 0-100
        "input_path":  input_path,
        "output_path": output_path,
        "error":       None,
        "class_counts": {},        # { class_name: count } accumulated over frames
    }


# ── Background Worker ─────────────────────────────────────────────────────────
def _run(job_id: str) -> None:
    """Runs in a daemon thread.  Reads, annotates, writes output video."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        return

    input_path: Path  = job["input_path"]
    output_path: Path = job["output_path"]

    try:
        # ── Open source video ──────────────────────────────────────────────
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV could not open video: {input_path.name}")

        fps    = cap.get(cv2.CAP_PROP_FPS) or 24.0
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        if width == 0 or height == 0:
            raise RuntimeError("Video has zero dimensions — file may be corrupt.")

        # ── Open output writer ─────────────────────────────────────────────
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        if not out.isOpened():
            raise RuntimeError("Failed to create output video writer.")

        _update(job_id, status="processing")

        counts: Dict[str, int] = {}
        ppe_counts: Dict[str, int] = {}
        frame_idx = 0

        if ppe_vision_model is None:
            raise RuntimeError("PPE model weights not loaded. Cannot process video.")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % FRAME_INTERVAL == 0:
                result   = ppe_vision_model.predict(frame)
                annotated = draw_annotations(frame, result)
                out.write(annotated)

                # Accumulate PPE class counts
                if result and result.boxes:
                    for box in result.boxes:
                        cls_id   = int(box.cls[0].cpu().numpy())
                        cls_name = result.names.get(cls_id, str(cls_id))
                        ppe_counts[cls_name] = ppe_counts.get(cls_name, 0) + 1
            else:
                out.write(frame)   # pass-through unannotated frame

            frame_idx += 1
            progress = int((frame_idx / total) * 100)
            _update(job_id, progress=progress, class_counts=ppe_counts, ppe_counts=ppe_counts)

        cap.release()
        out.release()

        _update(job_id, status="completed", progress=100, class_counts=ppe_counts, ppe_counts=ppe_counts)
        logger.info(f"[{job_id}] Video processing completed.")

        # Persist completed session to DB
        try:
            from db.database import SessionLocal
            from db import crud
            with SessionLocal() as db:
                with _JOBS_LOCK:
                    job_meta = dict(_JOBS.get(job_id, {}))
                crud.save_session(
                    db,
                    source_type="video",
                    class_counts=ppe_counts,
                    ppe_counts=ppe_counts,
                    filename=str(job_meta.get("input_path", "")).split("/")[-1].replace(f"{job_id}_in", "") or None,
                    status="completed",
                )
        except Exception:
            pass  # DB errors must not affect video result

    except Exception as exc:
        logger.exception(f"[{job_id}] Processing failed: {exc}")
        _update(job_id, status="failed", error=str(exc))
        # Persist failure to DB
        try:
            from db.database import SessionLocal
            from db import crud
            with SessionLocal() as db:
                crud.save_session(db, source_type="video", class_counts={}, status="failed", error_message=str(exc))
        except Exception:
            pass
        # Remove partial output
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass
    finally:
        # Always remove the raw upload file to free disk space
        if input_path.exists():
            try:
                input_path.unlink()
            except Exception:
                pass


def _update(job_id: str, **kwargs) -> None:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(kwargs)


# ── Public API ────────────────────────────────────────────────────────────────
def start_job(file_bytes: bytes, original_filename: str) -> str:
    """Save *file_bytes* to a temp file, register a job and kick off a thread.

    Returns the new ``job_id``.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    ext = Path(original_filename).suffix.lower() or ".mp4"
    input_path  = TEMP_DIR / f"{job_id}_in{ext}"
    output_path = TEMP_DIR / f"{job_id}_out.mp4"

    # Write upload to disk
    input_path.write_bytes(file_bytes)

    job = _make_job(job_id, input_path, output_path)
    with _JOBS_LOCK:
        _JOBS[job_id] = job

    t = threading.Thread(target=_run, args=(job_id,), daemon=True)
    t.start()

    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return job state dict or ``None`` if not found."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def get_output_path(job_id: str) -> Optional[Path]:
    """Return the output ``Path`` if job completed successfully, else ``None``."""
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job and job["status"] == "completed" and job["output_path"].exists():
        return job["output_path"]
    return None


def cleanup_job(job_id: str) -> None:
    """Delete job entry and any remaining temp files (call after client downloads)."""
    with _JOBS_LOCK:
        job = _JOBS.pop(job_id, None)
    if not job:
        return
    for key in ("input_path", "output_path"):
        p: Optional[Path] = job.get(key)
        if p and p.exists():
            try:
                p.unlink()
            except Exception:
                pass
