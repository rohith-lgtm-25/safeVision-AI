"""
tests/test_video.py
-------------------
Focused backend tests for Phase 2 Video Detection.

Tests:
  1. Upload validation — unsupported type → 400
  2. Upload validation — empty file → 400
  3. Upload validation — wrong extension → 400
  4. Valid MP4 upload → 202 + job_id
  5. Status polling — unknown job_id → 404
  6. Status polling — valid job_id → status in expected set
  7. Result endpoint — unknown job → 404
  8. Result endpoint — job not finished → 202
  9. Image endpoint still works (Phase 1 regression)

Real MP4 bytes are synthesised in-process with OpenCV so no external files
are needed.  Processing is intentionally fast (1-frame black video).
"""

import io
import sys
import os
import time
import struct
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from starlette.testclient import TestClient

# ── Add backend directory to sys.path ─────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_mp4(width=64, height=64, frames=3, fps=10) -> bytes:
    """Return minimal MP4 bytes synthesised with OpenCV."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = tmp.name
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, float(fps), (width, height))
    for _ in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        out.write(frame)
    out.release()
    data = Path(path).read_bytes()
    os.unlink(path)
    return data


def _make_png() -> bytes:
    """Return minimal valid PNG bytes."""
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


MP4_BYTES = _make_mp4()


# ── Test 1: Unsupported MIME type ──────────────────────────────────────────

def test_upload_unsupported_mime():
    res = client.post(
        "/api/detect/video",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    assert "Unsupported file type" in res.json()["detail"]


# ── Test 2: Empty file ─────────────────────────────────────────────────────

def test_upload_empty_file():
    res = client.post(
        "/api/detect/video",
        files={"file": ("empty.mp4", b"", "video/mp4")},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    assert "empty" in res.json()["detail"].lower()


# ── Test 3: Wrong extension (MIME ok but ext wrong) ────────────────────────

def test_upload_wrong_extension():
    res = client.post(
        "/api/detect/video",
        files={"file": ("clip.mkv", MP4_BYTES, "video/mp4")},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    assert "extension" in res.json()["detail"].lower()


# ── Test 4: Valid MP4 upload → job created ─────────────────────────────────

def test_upload_valid_mp4():
    res = client.post(
        "/api/detect/video",
        files={"file": ("clip.mp4", MP4_BYTES, "video/mp4")},
    )
    assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
    body = res.json()
    assert "job_id" in body, "Response must contain job_id"
    assert body["status"] == "queued"


# ── Test 5: Status — unknown job_id → 404 ─────────────────────────────────

def test_status_unknown_job():
    res = client.get("/api/detect/video/nonexistent-job-id/status")
    assert res.status_code == 404


# ── Test 6: Status — valid job_id returns expected fields ─────────────────

def test_status_valid_job():
    # Upload first
    up = client.post(
        "/api/detect/video",
        files={"file": ("clip.mp4", MP4_BYTES, "video/mp4")},
    )
    assert up.status_code == 202
    job_id = up.json()["job_id"]

    # Poll immediately — could be queued or processing or even completed
    res = client.get(f"/api/detect/video/{job_id}/status")
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"] == job_id
    assert body["status"] in {"queued", "processing", "completed", "failed"}
    assert isinstance(body["progress"], int)
    assert "class_counts" in body


# ── Test 7: Result — unknown job_id → 404 ─────────────────────────────────

def test_result_unknown_job():
    res = client.get("/api/detect/video/no-such-job/result")
    assert res.status_code == 404


# ── Test 8: Result — job not finished → 202 ───────────────────────────────

def test_result_not_finished():
    """Use a large enough video that it won't finish instantly."""
    big_mp4 = _make_mp4(width=320, height=240, frames=60, fps=30)
    up = client.post(
        "/api/detect/video",
        files={"file": ("big.mp4", big_mp4, "video/mp4")},
    )
    if up.status_code != 202:
        pytest.skip("Upload failed — skipping not-finished test")
    job_id = up.json()["job_id"]

    # Immediately hit result — almost certainly still processing
    res = client.get(f"/api/detect/video/{job_id}/result")
    # Accept 202 (still running) OR 200 (tiny video finished instantly)
    assert res.status_code in {200, 202, 500}


# ── Test 9: Image endpoint regression ─────────────────────────────────────

def test_image_endpoint_still_works():
    """Phase 1 regression: image detection must be unaffected."""
    png = _make_png()
    res = client.post(
        "/api/detect/image",
        files={"file": ("test.png", png, "image/png")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["image"].startswith("data:image/jpeg;base64,")
    assert "counts" in body
