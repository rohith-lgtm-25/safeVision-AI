from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from video_processing import (
    start_job,
    get_job,
    get_output_path,
    cleanup_job,
    MAX_VIDEO_BYTES,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
)
from pathlib import Path
import cv2
import numpy as np
import base64
from vision.model import ppe_vision_model
from vision.draw import draw_annotations

router = APIRouter()

@router.get("/")
def read_root():
    return {"message": "SafeVision API is up"}

# ── Shared inference helper ────────────────────────────────────────────────────

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB — shared by image and frame endpoints

def _run_inference_on_bytes(contents: bytes, imgsz: int = None, jpeg_quality: int = 90) -> dict:
    """Decode *contents* as an image, run the PPE model, return JSON-serialisable dict.

    Raises HTTPException on bad input or inference failure.
    """
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5 MB.")

    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not decode image data.")

    if ppe_vision_model is None:
        raise HTTPException(status_code=503, detail="PPE model weights not loaded. Check backend/weights/best.pt.")

    try:
        result = ppe_vision_model.predict(img, imgsz=imgsz)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference error: {exc}")

    annotated = draw_annotations(img, result)
    _, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    img_b64 = base64.b64encode(buf).decode("utf-8")

    # Collect PPE class counts (helmet / no_helmet / mask / no_mask)
    ppe_counts: dict = {}
    if result and result.boxes:
        for box in result.boxes:
            cls_id   = int(box.cls[0].cpu().numpy())
            cls_name = result.names.get(cls_id, str(cls_id))
            ppe_counts[cls_name] = ppe_counts.get(cls_name, 0) + 1

    return {
        "status":     "success",
        "image":      f"data:image/jpeg;base64,{img_b64}",
        "ppe_counts": ppe_counts,
        # Legacy alias kept so older frontend code still works
        "counts":     ppe_counts,
    }


@router.post("/detect/image")
async def detect_image(file: UploadFile = File(...)):
    """Phase 1 — single image upload → annotated result. Persists result to DB."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")
    import time
    t0 = time.monotonic()
    try:
        contents = await file.read()
        result_data = _run_inference_on_bytes(contents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Persist to DB — silently ignore DB errors so detection always succeeds
    try:
        from db.database import SessionLocal
        from db import crud
        duration = time.monotonic() - t0
        with SessionLocal() as db:
            crud.save_session(
                db,
                source_type="image",
                class_counts=result_data.get("ppe_counts", {}),
                ppe_counts=result_data.get("ppe_counts", {}),
                filename=file.filename,
                duration_seconds=round(duration, 3),
            )
    except Exception:
        pass  # DB errors must not break detection

    return JSONResponse(result_data)


# ── Phase 3: Webcam frame endpoint ────────────────────────────────────────────

@router.post("/detect/frame")
async def detect_frame(file: UploadFile = File(...)):
    """
    Accept a single JPEG frame captured from the browser webcam, run YOLO
    PPE inference with imgsz=416 for optimized low-latency performance,
    and return the annotated image as Base64.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Expected an image frame (JPEG or PNG).")
    try:
        contents = await file.read()
        return JSONResponse(_run_inference_on_bytes(contents, imgsz=416, jpeg_quality=80))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Phase 2: Video Detection ──────────────────────────────────────────────────

@router.post("/detect/video")
async def upload_video(
    file: UploadFile = File(...),
    frame_interval: int = 5,
) -> JSONResponse:
    """
    Accept a video upload, validate it, and start asynchronous YOLO processing.

    Returns a ``job_id`` that the client uses to poll /detect/video/{id}/status.

    NOTE: Current model is COCO-pretrained (80 classes).  Custom PPE classes
    (helmet / mask) are not yet available.
    """
    # ── MIME type check ────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: MP4, MOV, AVI.",
        )

    # ── Extension check ────────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported extension '{suffix}'. Allowed: .mp4, .mov, .avi.",
        )

    # ── Read and size-check ────────────────────────────────────────────────
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read upload: {e}")

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_VIDEO_BYTES // (1024*1024)} MB.",
        )

    # ── Actual video validation via OpenCV ─────────────────────────────────
    # Write to a tiny temp buffer and check that OpenCV can decode at least one frame.
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    try:
        cap = __import__("cv2").VideoCapture(tmp_path)
        valid = cap.isOpened() and cap.get(__import__("cv2").CAP_PROP_FRAME_COUNT) > 0
        cap.release()
    finally:
        os.unlink(tmp_path)
    if not valid:
        raise HTTPException(status_code=400, detail="File does not appear to be a valid video.")

    # ── Start background job ───────────────────────────────────────────────
    interval = max(1, frame_interval)
    # Temporarily inject the interval into the env so _run() picks it up.
    # (Simple approach — fine for a hackathon singleton.)
    import video_processing as vp
    vp.FRAME_INTERVAL = interval

    job_id = start_job(contents, file.filename or "upload.mp4")
    return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)


@router.get("/detect/video/{job_id}/status")
def video_status(job_id: str) -> JSONResponse:
    """Poll processing status.  Returns status, progress (0-100), and per-class detection counts."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JSONResponse({
        "job_id":       job_id,
        "status":       job["status"],
        "progress":     job["progress"],
        "class_counts": job.get("class_counts", {}),
        "error":        job.get("error"),
    })


@router.get("/detect/video/{job_id}/result")
def video_result(job_id: str) -> FileResponse:
    """Download or stream the completed annotated video.  Cleans up temp files after serving."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] == "processing" or job["status"] == "queued":
        raise HTTPException(status_code=202, detail="Video is still processing.")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Job failed: {job.get('error', 'unknown error')}")

    output_path = get_output_path(job_id)
    if output_path is None:
        raise HTTPException(status_code=500, detail="Output file not found.")

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=f"safevision_{job_id[:8]}_annotated.mp4",
    )
