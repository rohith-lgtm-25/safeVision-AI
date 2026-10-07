import sys
import os
import io
import cv2
import numpy as np
from fastapi.testclient import TestClient
from main import app
from vision.model import safe_vision_model

client = TestClient(app)

def run_audit():
    results = {"passed": [], "failed": [], "model_info": {}}
    
    # 1. TEST 1: BACKEND Health
    try:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
        results["passed"].append("TEST 1: Backend health endpoint responding correctly.")
    except Exception as e:
        results["failed"].append(f"TEST 1: Backend health endpoint failed - {str(e)}")

    # Test 1 & 6: Model init & custom readiness
    try:
        assert safe_vision_model.model is not None
        device = safe_vision_model.device.type
        results["passed"].append(f"TEST 1: Model initialized on device: {device}")
        
        # Check actual model classes (Test 6)
        names = safe_vision_model.model.names
        results["model_info"]["class_count"] = len(names)
        results["model_info"]["sample_classes"] = list(names.values())[:5]
        
        if len(names) == 80 and names.get(0) == 'person':
            results["model_info"]["type"] = "COCO pretrained YOLO11n (NOT custom PPE model)"
            results["passed"].append("TEST 6: Identified as COCO base model. Custom PPE model not yet applied.")
        else:
            results["model_info"]["type"] = "Custom Model"
    except Exception as e:
        results["failed"].append(f"TEST 1/6: Model init check failed - {str(e)}")

    # 2. TEST 2: IMAGE UPLOAD
    try:
        # Valid PNG
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        _, png_buf = cv2.imencode('.png', img)
        res_png = client.post("/api/detect/image", files={"file": ("test.png", png_buf.tobytes(), "image/png")})
        assert res_png.status_code == 200
        assert "image" in res_png.json()
        results["passed"].append("TEST 2: Valid PNG upload successful.")
        
        # Unsupported format (e.g. text file pretending to be image or just sending application/json)
        res_txt = client.post("/api/detect/image", files={"file": ("test.txt", b"hello world", "text/plain")})
        assert res_txt.status_code == 400
        results["passed"].append("TEST 2: Unsupported file extension rejected properly.")
        
        # Corrupted image (sending bad bytes as image/jpeg)
        res_corrupt = client.post("/api/detect/image", files={"file": ("bad.jpg", b"corrupted bytes", "image/jpeg")})
        assert res_corrupt.status_code == 400
        results["passed"].append("TEST 2: Corrupted image handled gracefully.")
        
        # Empty upload - fast api requires file
        res_empty = client.post("/api/detect/image", files={"file": ("empty.jpg", b"", "image/jpeg")})
        # Wait, cv2.imdecode might fail with 400 if empty. Let's see what it returns.
        if res_empty.status_code == 400:
            results["passed"].append("TEST 2: Empty upload handled gracefully.")
        else:
            results["failed"].append(f"TEST 2: Empty upload did not return 400. Returned {res_empty.status_code}")
    except Exception as e:
        import traceback
        results["failed"].append(f"TEST 2: Image upload tests failed - {traceback.format_exc()}")

    # 3. TEST 3: AI Inference
    try:
        # Post a real image and check result structure
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        _, jpg_buf = cv2.imencode('.jpg', img)
        res_inf = client.post("/api/detect/image", files={"file": ("test.jpg", jpg_buf.tobytes(), "image/jpeg")})
        assert res_inf.status_code == 200
        data = res_inf.json()
        assert "counts" in data
        assert "image" in data
        assert data["image"].startswith("data:image/jpeg;base64,")
        results["passed"].append("TEST 3: AI Inference executed and Base64 image returned.")
    except Exception as e:
        results["failed"].append(f"TEST 3: AI inference tests failed - {str(e)}")

    import json
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_audit()
