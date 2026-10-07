import torch
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)

class SafeVisionModel:
    def __init__(self, weights_path="yolo11n.pt"):
        self.device = self._get_device()
        logger.info(f"Loading YOLO model on device: {self.device}")
        
        # Load the model
        try:
            self.model = YOLO(weights_path)
            self.model.to(self.device)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model = None

    def _get_device(self):
        # MPS causes fatal crashes when two YOLO models run simultaneously
        # in separate threads (video processing). Use CPU for stability.
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def predict(self, image, conf_threshold=0.25, imgsz=None):
        if self.model is None:
            raise ValueError("Model not loaded")
        
        # Run inference
        kwargs = {"conf": conf_threshold, "device": self.device}
        if imgsz is not None:
            kwargs["imgsz"] = imgsz
        results = self.model(image, **kwargs)
        return results[0] # Return the first (and only) result object

# ── PPE-only singleton ────────────────────────────────────────────────────────
# COCO detection has been removed. Only best.pt (4-class PPE model) is loaded.

import os as _os
_PPE_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "weights", "best.pt")

if not _os.path.exists(_PPE_PATH):
    logger.error(f"PPE weights not found at {_PPE_PATH}. All inference calls will fail.")

ppe_vision_model = SafeVisionModel(_PPE_PATH) if _os.path.exists(_PPE_PATH) else None

# Alias for any legacy imports
detection_model = ppe_vision_model
safe_vision_model = ppe_vision_model
