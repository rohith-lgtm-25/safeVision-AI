import cv2
import numpy as np

CLASS_COLORS = {
    0: (255, 0, 0),      # helmet
    1: (0, 0, 255),      # no_helmet
    2: (0, 255, 0),      # mask
    3: (0, 165, 255),    # no_mask
}

def draw_annotations(image: np.ndarray, result) -> np.ndarray:
    annotated_img = image.copy()

    if result is None or result.boxes is None or len(result.boxes) == 0:
        return annotated_img

    # Get values once instead of converting every value individually
    boxes = result.boxes.xyxy.cpu().numpy().astype(int)
    confidences = result.boxes.conf.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), conf, cls_id in zip(
        boxes, confidences, classes
    ):
        cls_name = result.names.get(cls_id, str(cls_id))
        color = CLASS_COLORS.get(cls_id, (128, 128, 128))

        cv2.rectangle(
            annotated_img,
            (x1, y1),
            (x2, y2),
            color,
            2
        )

        label = f"{cls_name} {conf:.2f}"

        cv2.putText(
            annotated_img,
            label,
            (x1, max(y1 - 8, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

    return annotated_img