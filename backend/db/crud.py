"""
db/crud.py
----------
All database read/write helpers used by API endpoints.
"""
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from db.models import DetectionSession, SourceType


# ── Write helpers ─────────────────────────────────────────────────────────────

def save_session(
    db: Session,
    source_type: str,
    class_counts: Dict[str, int],
    ppe_counts: Optional[Dict[str, int]] = None,
    status: str = "completed",
    filename: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    error_message: Optional[str] = None,
) -> DetectionSession:
    """Create and persist a new DetectionSession row."""
    total = sum(class_counts.values()) if class_counts else 0
    if ppe_counts:
        total += sum(ppe_counts.values())
        
    session = DetectionSession(
        source_type=SourceType(source_type),
        status=status,
        filename=filename,
        duration_seconds=duration_seconds,
        total_detections=total,
        error_message=error_message,
    )
    session.class_counts = class_counts or {}
    
    import json
    session.ppe_counts_json = json.dumps(ppe_counts) if ppe_counts is not None else None
    
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_sessions(
    db: Session,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[DetectionSession]:
    q = db.query(DetectionSession)
    if source_type:
        q = q.filter(DetectionSession.source_type == SourceType(source_type))
    if status:
        q = q.filter(DetectionSession.status == status)
    return q.order_by(desc(DetectionSession.created_at)).offset(offset).limit(limit).all()


def count_sessions(
    db: Session,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    q = db.query(func.count(DetectionSession.id))
    if source_type:
        q = q.filter(DetectionSession.source_type == SourceType(source_type))
    if status:
        q = q.filter(DetectionSession.status == status)
    return q.scalar() or 0


def get_session_by_id(db: Session, session_id: int) -> Optional[DetectionSession]:
    return db.query(DetectionSession).filter(DetectionSession.id == session_id).first()


# ── Dashboard statistics ──────────────────────────────────────────────────────

def get_dashboard_stats(db: Session) -> dict:
    """Aggregate statistics across all sessions for the dashboard."""
    total_sessions   = count_sessions(db)
    image_sessions   = count_sessions(db, source_type="image")
    video_sessions   = count_sessions(db, source_type="video")
    webcam_sessions  = count_sessions(db, source_type="webcam")
    failed_sessions  = count_sessions(db, status="failed")

    total_detections_row = db.query(
        func.sum(DetectionSession.total_detections)
    ).scalar()
    total_detections = int(total_detections_row or 0)

    # Aggregate class counts across all sessions
    all_sessions = db.query(DetectionSession).filter(
        DetectionSession.status == "completed"
    ).all()
    aggregated_counts: Dict[str, int] = {}
    aggregated_ppe_counts: Dict[str, int] = {}
    
    for s in all_sessions:
        for cls, cnt in s.class_counts.items():
            aggregated_counts[cls] = aggregated_counts.get(cls, 0) + cnt
        
        if s.ppe_counts:
            for cls, cnt in s.ppe_counts.items():
                aggregated_ppe_counts[cls] = aggregated_ppe_counts.get(cls, 0) + cnt

    # Recent 7 days daily breakdown
    daily: Dict[str, int] = {}
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = (
        db.query(DetectionSession)
        .filter(DetectionSession.created_at >= seven_days_ago)
        .all()
    )
    for s in recent:
        day = s.created_at.strftime("%Y-%m-%d")
        daily[day] = daily.get(day, 0) + 1

    # Sort by top detected classes
    top_classes = sorted(aggregated_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_ppe_classes = sorted(aggregated_ppe_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_sessions":    total_sessions,
        "image_sessions":    image_sessions,
        "video_sessions":    video_sessions,
        "webcam_sessions":   webcam_sessions,
        "failed_sessions":   failed_sessions,
        "total_detections":  total_detections,
        "top_classes":       [{"class": k, "count": v} for k, v in top_classes],
        "top_ppe_classes":   [{"class": k, "count": v} for k, v in top_ppe_classes],
        "daily_sessions":    [{"date": k, "count": v} for k, v in sorted(daily.items())],
        "model_note":        "Dual models active: COCO + PPE.",
    }
