"""
db/models.py
------------
ORM model for a single detection session.

A "session" is one of:
  - image  : a single image upload processed synchronously
  - video  : a completed video processing job
  - webcam : a webcam monitoring session summary (aggregated, not per-frame)

IMPORTANT: class_counts stores actual COCO class detections from the
pretrained yolo11n model.  PPE-specific counts (helmet / mask) are always
null until custom fine-tuned weights are trained and deployed.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
import enum

from db.database import Base


class SourceType(str, enum.Enum):
    image  = "image"
    video  = "video"
    webcam = "webcam"


class DetectionSession(Base):
    __tablename__ = "detection_sessions"

    id                = Column(Integer, primary_key=True, index=True)
    source_type       = Column(Enum(SourceType), nullable=False, index=True)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    status            = Column(String(20), nullable=False, default="completed")  # completed | failed | processing
    filename          = Column(String(255), nullable=True)   # original upload filename (may be None for webcam)
    duration_seconds  = Column(Float, nullable=True)         # processing wall-clock time
    total_detections  = Column(Integer, nullable=False, default=0)
    # JSON blob: { "person": 12, "car": 3, … }  — COCO classes only
    class_counts_json = Column(Text, nullable=False, default="{}")
    # Always null until custom PPE model is trained
    ppe_counts_json   = Column(Text, nullable=True)
    error_message     = Column(Text, nullable=True)

    # ── helpers ──────────────────────────────────────────────────────────────
    @property
    def class_counts(self) -> dict:
        try:
            return json.loads(self.class_counts_json or "{}")
        except Exception:
            return {}

    @class_counts.setter
    def class_counts(self, value: dict):
        self.class_counts_json = json.dumps(value or {})

    @property
    def ppe_counts(self) -> dict | None:
        try:
            return json.loads(self.ppe_counts_json) if self.ppe_counts_json else None
        except Exception:
            return None

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "source_type":      self.source_type,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "status":           self.status,
            "filename":         self.filename,
            "duration_seconds": self.duration_seconds,
            "total_detections": self.total_detections,
            "class_counts":     self.class_counts,
            "ppe_counts":       self.ppe_counts,
            "error_message":    self.error_message,
        }
