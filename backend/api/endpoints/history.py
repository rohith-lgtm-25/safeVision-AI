"""
api/endpoints/history.py
------------------------
Endpoints for detection history and dashboard statistics.

GET /api/history            — paginated list of sessions with optional filters
GET /api/history/{id}       — single session detail
POST /api/history/webcam    — save a webcam session summary from the frontend
GET /api/dashboard/stats    — aggregated statistics for the dashboard
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WebcamSessionCreate(BaseModel):
    total_frames_sent: int
    total_detections: int
    class_counts: dict
    ppe_counts: Optional[dict] = None
    duration_seconds: Optional[float] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/history")
def list_history(
    source_type: Optional[str] = Query(None, description="Filter by source: image, video, webcam"),
    status: Optional[str]      = Query(None, description="Filter by status: completed, failed"),
    limit: int                  = Query(50, ge=1, le=200),
    offset: int                 = Query(0, ge=0),
    db: Session                 = Depends(get_db),
):
    """Paginated detection history, newest first."""
    # Validate enum values before hitting the DB to return a clean 400
    VALID_SOURCES = {"image", "video", "webcam"}
    VALID_STATUSES = {"completed", "failed", "processing"}
    if source_type and source_type not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type. Choose from: {VALID_SOURCES}")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {VALID_STATUSES}")

    try:
        sessions = crud.get_sessions(db, source_type=source_type, status=status, limit=limit, offset=offset)
        total    = crud.count_sessions(db, source_type=source_type, status=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return JSONResponse({
        "total":   total,
        "limit":   limit,
        "offset":  offset,
        "results": [s.to_dict() for s in sessions],
    })


@router.get("/history/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Return a single session by ID."""
    session = crud.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return JSONResponse(session.to_dict())


@router.post("/history/webcam", status_code=201)
def save_webcam_session(payload: WebcamSessionCreate, db: Session = Depends(get_db)):
    """
    Persist a webcam monitoring session summary submitted by the frontend.
    Stores aggregate class counts, not individual frames.
    """
    if payload.total_frames_sent < 0 or payload.total_detections < 0:
        raise HTTPException(status_code=400, detail="Counts must be non-negative.")
    try:
        session = crud.save_session(
            db,
            source_type="webcam",
            class_counts=payload.class_counts or {},
            ppe_counts=payload.ppe_counts,
            duration_seconds=payload.duration_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    return JSONResponse(session.to_dict(), status_code=201)


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    """Aggregated statistics for the dashboard: totals, top classes, daily counts."""
    try:
        stats = crud.get_dashboard_stats(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    return JSONResponse(stats)
