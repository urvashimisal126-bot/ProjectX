"""
YOLOv8 detection module.
Loads model once with st.cache_resource.
Falls back to Demo Mode if models/best.pt is missing.
"""

from __future__ import annotations

import os
import io
import random
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

MODEL_PATH = Path("models/best.pt")
DEMO_MODE  = not MODEL_PATH.exists()

# Severity colour palette for demo boxes
_BOX_COLORS = {
    "pothole":     (200, 55, 45),
    "road_damage": (224, 138, 30),
    "streetlight": (43, 158, 107),
    "drain":       (47, 111, 181),
}
_DEFAULT_COLOR = (100, 100, 200)


class Detection(NamedTuple):
    class_name: str
    confidence: float
    box: tuple[int, int, int, int]   # x1, y1, x2, y2 in pixels
    area_ratio: float


class DetectionResult(NamedTuple):
    detections: list[Detection]
    annotated_image: Image.Image   # PIL image with boxes drawn
    demo_mode: bool


# ─── Model loader (cached) ───────────────────────────────────────────────────

def _load_model():
    if DEMO_MODE:
        return None
    try:
        from ultralytics import YOLO  # noqa: PLC0415
        return YOLO(str(MODEL_PATH))
    except Exception:
        return None


try:
    import streamlit as st
    @st.cache_resource(show_spinner=False)
    def get_model():
        return _load_model()
except ImportError:
    def get_model():  # type: ignore[misc]
        return _load_model()


# ─── Image detection ─────────────────────────────────────────────────────────

def detect_image(
    image_path: str,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
) -> DetectionResult:
    """Run detection on an image file. Returns DetectionResult."""
    img = Image.open(image_path).convert("RGB")
    model = get_model()

    if model is None or DEMO_MODE:
        return _demo_detections(img, class_list)

    try:
        results = model.predict(source=image_path, conf=conf_threshold, verbose=False)
        return _parse_results(results[0], img, class_list)
    except Exception:
        return _demo_detections(img, class_list)


def detect_image_pil(
    img: Image.Image,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
) -> DetectionResult:
    """Run detection on a PIL image."""
    import tempfile, os as _os  # noqa: PLC0415
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name)
        tmp_path = tmp.name
    try:
        return detect_image(tmp_path, conf_threshold, class_list)
    finally:
        _os.unlink(tmp_path)


def _parse_results(result, img: Image.Image, class_list: list[str] | None) -> DetectionResult:
    from core.config import ISSUE_CLASSES  # noqa: PLC0415
    allowed = set(class_list or ISSUE_CLASSES)
    w, h = img.size
    detections: list[Detection] = []

    if result.boxes is not None:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            name = result.names[cls_id]
            if name not in allowed:
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
            detections.append(Detection(name, conf, (x1, y1, x2, y2), area_ratio))

    annotated = _draw_boxes(img, detections)
    return DetectionResult(detections, annotated, False)


def _demo_detections(img: Image.Image, class_list: list[str] | None) -> DetectionResult:
    from core.config import ISSUE_CLASSES  # noqa: PLC0415
    allowed = class_list or ISSUE_CLASSES
    w, h = img.size
    count = random.randint(1, 3)
    detections = []
    for _ in range(count):
        cls = random.choice(allowed)
        conf = round(random.uniform(0.50, 0.92), 2)
        bw = random.randint(w // 6, w // 3)
        bh = random.randint(h // 6, h // 3)
        x1 = random.randint(0, w - bw)
        y1 = random.randint(0, h - bh)
        x2, y2 = x1 + bw, y1 + bh
        area_ratio = (bw * bh) / (w * h)
        detections.append(Detection(cls, conf, (x1, y1, x2, y2), area_ratio))
    annotated = _draw_boxes(img, detections)
    return DetectionResult(detections, annotated, True)


def _draw_boxes(img: Image.Image, detections: list[Detection]) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.load_default(size=14)
    except Exception:
        font = ImageFont.load_default()

    for det in detections:
        color = _BOX_COLORS.get(det.class_name, _DEFAULT_COLOR)
        x1, y1, x2, y2 = det.box
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = f"{det.class_name} {det.confidence:.0%}"
        draw.rectangle([x1, y1 - 18, x1 + len(label) * 8, y1], fill=color)
        draw.text((x1 + 2, y1 - 16), label, fill="white", font=font)
    return out


# ─── Video detection ─────────────────────────────────────────────────────────

def detect_video(
    video_path: str,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
    sample_fps: int = 1,
) -> DetectionResult:
    """
    Sample one frame per second, run detection, return the frame with
    the most/highest-confidence detections.
    Falls back to demo if cv2 is unavailable.
    """
    try:
        import cv2  # noqa: PLC0415
    except ImportError:
        return DetectionResult([], Image.new("RGB", (640, 480), (200, 200, 200)), True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    interval = int(fps / max(sample_fps, 1))

    best_result: DetectionResult | None = None
    best_score = -1.0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            result = detect_image_pil(pil_img, conf_threshold, class_list)
            score = sum(d.confidence for d in result.detections)
            if score > best_score:
                best_score = score
                best_result = result
        frame_idx += 1

    cap.release()

    if best_result is None:
        return _demo_detections(Image.new("RGB", (640, 480), (200, 200, 200)), class_list)
    return best_result
