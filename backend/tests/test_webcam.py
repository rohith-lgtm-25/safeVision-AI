"""
tests/test_webcam.py
--------------------
Focused backend tests for Phase 3 Webcam Frame Endpoint.

Tests:
  1. Valid JPEG frame → 200 + annotated image + coco_counts
  2. Valid PNG frame  → 200
  3. Non-image content type → 400
  4. Empty payload → 400
  5. Oversized frame → 413
  6. Corrupted bytes (image/* MIME but invalid data) → 400
  7. Phase 1 regression: /detect/image still works
  8. Phase 2 regression: /detect/video upload still returns 202
"""

import sys
import os
from pathlib import Path

import cv2
import numpy as np
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_jpeg(width=64, height=64) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()

def _make_png(width=64, height=64) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()

def _make_mp4(frames=3) -> bytes:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = tmp.name
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 32))
    for _ in range(frames):
        out.write(np.zeros((32, 32, 3), dtype=np.uint8))
    out.release()
    data = Path(path).read_bytes()
    os.unlink(path)
    return data

JPEG = _make_jpeg()
PNG  = _make_png()
MP4  = _make_mp4()


# ── Test 1: Valid JPEG → 200 ──────────────────────────────────────────────────

def test_frame_valid_jpeg():
    res = client.post(
        "/api/detect/frame",
        files={"file": ("frame.jpg", JPEG, "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["image"].startswith("data:image/jpeg;base64,")
    assert "ppe_counts" in body
    assert isinstance(body["ppe_counts"], dict)


# ── Test 2: Valid PNG → 200 ───────────────────────────────────────────────────

def test_frame_valid_png():
    res = client.post(
        "/api/detect/frame",
        files={"file": ("frame.png", PNG, "image/png")},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "success"


# ── Test 3: Non-image MIME → 400 ─────────────────────────────────────────────

def test_frame_non_image_mime():
    res = client.post(
        "/api/detect/frame",
        files={"file": ("data.txt", b"hello world", "text/plain")},
    )
    assert res.status_code == 400, res.text
    assert "image" in res.json()["detail"].lower()


# ── Test 4: Empty payload → 400 ──────────────────────────────────────────────

def test_frame_empty_payload():
    res = client.post(
        "/api/detect/frame",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert res.status_code == 400, res.text
    assert "empty" in res.json()["detail"].lower()


# ── Test 5: Oversized frame → 413 ────────────────────────────────────────────

def test_frame_oversized():
    big = b"\xff\xd8\xff" + b"X" * (5 * 1024 * 1024 + 1)   # > 5 MB
    res = client.post(
        "/api/detect/frame",
        files={"file": ("big.jpg", big, "image/jpeg")},
    )
    assert res.status_code == 413, res.text


# ── Test 6: Corrupted bytes → 400 ────────────────────────────────────────────

def test_frame_corrupted_bytes():
    res = client.post(
        "/api/detect/frame",
        files={"file": ("bad.jpg", b"not really a jpeg", "image/jpeg")},
    )
    assert res.status_code == 400, res.text


# ── Test 7: Phase 1 regression — /detect/image still works ───────────────────

def test_regression_detect_image():
    res = client.post(
        "/api/detect/image",
        files={"file": ("test.png", PNG, "image/png")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["image"].startswith("data:image/jpeg;base64,")
    assert "counts" in body      # legacy PPE keys still present
    assert "ppe_counts" in body  # ppe_counts field present


# ── Test 8: Phase 2 regression — /detect/video still accepts MP4 ─────────────

def test_regression_detect_video():
    res = client.post(
        "/api/detect/video",
        files={"file": ("clip.mp4", MP4, "video/mp4")},
    )
    assert res.status_code == 202, res.text
    assert "job_id" in res.json()
