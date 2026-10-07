"""
tests/test_db.py
----------------
Focused backend tests for Phase 4: database, history, and dashboard endpoints.

Tests:
  1. DB init creates tables
  2. save_session — image type persisted correctly
  3. save_session — counts are stored and retrieved
  4. GET /history returns 200 with results list
  5. GET /history?source_type=image filters correctly
  6. GET /history?source_type=invalid returns 400
  7. GET /history/{id} returns session detail
  8. GET /history/{id} with nonexistent id returns 404
  9. POST /history/webcam saves webcam summary
 10. POST /history/webcam with negative counts returns 400
 11. GET /dashboard/stats returns expected keys
 12. Phase 1 regression: /detect/image still works
 13. Phase 2 regression: /detect/video still accepts MP4
"""
import sys
import os
from pathlib import Path
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force an in-memory SQLite for tests so we don't pollute the real DB
import db.database as _dbmod
from sqlalchemy.pool import StaticPool

_dbmod.DATABASE_URL  = "sqlite:///:memory:"
_dbmod.engine        = __import__("sqlalchemy").create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_dbmod.SessionLocal  = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
    autocommit=False, autoflush=False, bind=_dbmod.engine
)

from db.database import init_db, SessionLocal
from db import crud, models

from starlette.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Setup ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables before each test."""
    init_db()
    yield
    models.Base.metadata.drop_all(bind=_dbmod.engine)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _png():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()

def _mp4():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (32, 32))
    for _ in range(3):
        out.write(np.zeros((32, 32, 3), dtype=np.uint8))
    out.release()
    data = Path(path).read_bytes()
    os.unlink(path)
    return data


# ── Test 1: DB init ───────────────────────────────────────────────────────────

def test_db_init_creates_tables():
    from sqlalchemy import inspect
    inspector = inspect(_dbmod.engine)
    assert "detection_sessions" in inspector.get_table_names()


# ── Test 2: save_session — basic persistence ──────────────────────────────────

def test_save_session_image():
    with SessionLocal() as db:
        s = crud.save_session(db, source_type="image", class_counts={"person": 3})
    assert s.id is not None
    assert s.source_type == models.SourceType.image
    assert s.total_detections == 3

def test_save_session_ppe_counts():
    with SessionLocal() as db:
        s = crud.save_session(
            db, 
            source_type="image", 
            class_counts={"person": 2}, 
            ppe_counts={"helmet": 1, "no_mask": 1}
        )
    assert s.id is not None
    assert s.class_counts == {"person": 2}
    assert s.ppe_counts == {"helmet": 1, "no_mask": 1}
    assert s.total_detections == 4


# ── Test 3: class counts round-trip ──────────────────────────────────────────

def test_save_session_counts_roundtrip():
    counts = {"person": 5, "car": 2, "bicycle": 1}
    with SessionLocal() as db:
        s = crud.save_session(db, source_type="video", class_counts=counts)
        fetched = crud.get_session_by_id(db, s.id)
    assert fetched.class_counts == counts
    assert fetched.total_detections == 8


# ── Test 4: GET /history — returns list ───────────────────────────────────────

def test_history_list():
    with SessionLocal() as db:
        crud.save_session(db, source_type="image", class_counts={"person": 1})
    res = client.get("/api/history")
    assert res.status_code == 200
    body = res.json()
    assert "results" in body
    assert body["total"] >= 1


# ── Test 5: GET /history?source_type=image filter ─────────────────────────────

def test_history_filter_source():
    with SessionLocal() as db:
        crud.save_session(db, source_type="image", class_counts={})
        crud.save_session(db, source_type="video", class_counts={})
    res = client.get("/api/history?source_type=image")
    assert res.status_code == 200
    results = res.json()["results"]
    assert all(r["source_type"] == "image" for r in results)


# ── Test 6: GET /history?source_type=invalid → 400 ───────────────────────────

def test_history_invalid_source():
    res = client.get("/api/history?source_type=foobar")
    assert res.status_code == 400


# ── Test 7: GET /history/{id} — detail ────────────────────────────────────────

def test_history_detail():
    with SessionLocal() as db:
        s = crud.save_session(db, source_type="webcam", class_counts={"person": 2})
    res = client.get(f"/api/history/{s.id}")
    assert res.status_code == 200
    assert res.json()["id"] == s.id


# ── Test 8: GET /history/{id} nonexistent → 404 ──────────────────────────────

def test_history_detail_not_found():
    res = client.get("/api/history/999999")
    assert res.status_code == 404


# ── Test 9: POST /history/webcam saves summary ────────────────────────────────

def test_webcam_session_save():
    payload = {
        "total_frames_sent": 30,
        "total_detections": 45,
        "class_counts": {"person": 45},
        "duration_seconds": 30.0,
    }
    res = client.post("/api/history/webcam", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["source_type"] == "webcam"
    assert body["class_counts"]["person"] == 45


# ── Test 10: POST /history/webcam — negative counts → 400 ────────────────────

def test_webcam_session_negative_counts():
    payload = {
        "total_frames_sent": -1,
        "total_detections": -5,
        "class_counts": {},
    }
    res = client.post("/api/history/webcam", json=payload)
    assert res.status_code == 400


# ── Test 11: GET /dashboard/stats — expected keys ─────────────────────────────

def test_dashboard_stats_keys():
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    body = res.json()
    for key in ("total_sessions", "total_detections", "top_classes", "daily_sessions", "model_note"):
        assert key in body, f"Missing key: {key}"
    assert "PPE" in body["model_note"] or "COCO" in body["model_note"]


# ── Test 12: Phase 1 regression ───────────────────────────────────────────────

def test_regression_detect_image():
    res = client.post("/api/detect/image", files={"file": ("t.png", _png(), "image/png")})
    assert res.status_code == 200
    assert res.json()["status"] == "success"


# ── Test 13: Phase 2 regression ───────────────────────────────────────────────

def test_regression_detect_video():
    res = client.post("/api/detect/video", files={"file": ("clip.mp4", _mp4(), "video/mp4")})
    assert res.status_code == 202
    assert "job_id" in res.json()
