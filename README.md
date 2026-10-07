# safeVision-AI


### AI-Powered PPE Detection and Workplace Safety Monitoring

SafeVision AI is an AI-powered computer vision system designed to automatically monitor Personal Protective Equipment (PPE) compliance in construction and industrial environments.

The system uses a custom-trained **YOLO11n object detection model** with transfer learning to detect:

- 🪖 Helmet
- ❌ No Helmet
- 😷 Mask
- ❌ No Mask

SafeVision AI supports **image detection, video detection, and live webcam monitoring**, with detection history stored using SQLite.

---

## 🚀 Features

- 📷 **Image Detection**
  - Upload an image and detect PPE compliance.
  - Displays bounding boxes and confidence scores.

- 🎥 **Video Detection**
  - Process uploaded videos frame-by-frame.
  - Detect PPE violations throughout the video.

- 📹 **Live Webcam Monitoring**
  - Real-time webcam preview.
  - Periodic AI inference for PPE detection.
  - Configurable frame capture interval.
  - Smooth camera preview with controlled AI inference.

- 🧠 **Custom PPE Detection Model**
  - Custom-trained YOLO11n model.
  - Fine-tuned using transfer learning.
  - Detects four PPE classes.

- 📊 **Dashboard**
  - View PPE detection statistics.
  - Visualize detection results.

- 🗂️ **Detection History**
  - Stores detection session summaries.
  - Tracks PPE detection counts and timestamps.

- 🎯 **Confidence Scores**
  - Each detected PPE object includes its confidence score.

---

# 🧠 AI Model

SafeVision AI uses **YOLO11n** for object detection.

Instead of training a model completely from scratch, we use **transfer learning**.

### Transfer Learning Workflow

```text
Pretrained YOLO11n
        ↓
PPE Dataset
        ↓
Fine-Tuning
        ↓
Custom PPE Model
        ↓
best.pt
