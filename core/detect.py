"""
Hybrid Detection Engine: YOLOv8 + Google Gemini.
Supports detector modes: 'yolo', 'gemini', and 'hybrid'.
Always degrades gracefully if offline or API key is absent.
"""

from __future__ import annotations

import os
import io
import random
from pathlib import Path
from typing import NamedTuple, Any
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.config import (
    DETECTOR, GEMINI_DEFAULT_CONFIDENCE, ISSUE_CLASSES
)
from core.ai_assess import assess_image, AIAssessment, BoundingBox

MODEL_PATH = Path("models/best.pt")
DEMO_MODE  = not MODEL_PATH.exists()

# Severity colour palette for demo/annotated boxes
_BOX_COLORS = {
    "pothole":     (200, 55, 45),
    "road_damage": (224, 138, 30),
    "streetlight": (43, 158, 107),
    "drain":       (47, 111, 181),
}
_DEFAULT_COLOR = (100, 100, 200)


class Detection:
    def __init__(
        self,
        class_name: str,
        confidence: float | None,
        box: tuple[int, int, int, int],  # x1, y1, x2, y2 in pixels
        area_ratio: float,
        source: str = "yolo",            # "yolo" or "gemini"
        confidence_source: str = "measured",  # "measured" or "gemini_estimate"
    ):
        self.class_name = class_name
        self.confidence = confidence
        self.box = box
        self.area_ratio = area_ratio
        self.source = source
        self.confidence_source = confidence_source

    def to_dict(self) -> dict:
        return {
            "class_name": self.class_name,
            "confidence": self.confidence,
            "box": self.box,
            "area_ratio": self.area_ratio,
            "source": self.source,
            "confidence_source": self.confidence_source,
        }

    def __repr__(self) -> str:
        conf_str = f"{self.confidence:.2f}" if self.confidence is not None else "est"
        return f"Detection({self.class_name}, {conf_str}, src={self.source})"


class DetectionResult(NamedTuple):
    detections: list[Detection]
    annotated_image: Image.Image
    demo_mode: bool
    detector_used: str = "yolo"
    assessment: AIAssessment | None = None


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

def run_yolo_detection(
    img: Image.Image,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
) -> tuple[list[Detection], bool]:
    """Run YOLO model or demo mode fallback. Returns (detections, is_demo_mode)."""
    model = get_model()
    if model is None or DEMO_MODE:
        return _demo_detections_list(img, class_list), True

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name)
        tmp_path = tmp.name

    try:
        results = model.predict(source=tmp_path, conf=conf_threshold, verbose=False)
        return _parse_yolo_boxes(results[0], img, class_list), False
    except Exception:
        return _demo_detections_list(img, class_list), True
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _parse_yolo_boxes(result, img: Image.Image, class_list: list[str] | None) -> list[Detection]:
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
            detections.append(Detection(
                class_name=name,
                confidence=conf,
                box=(x1, y1, x2, y2),
                area_ratio=area_ratio,
                source="yolo",
                confidence_source="measured",
            ))
    return detections


def _convert_gemini_boxes_to_detections(
    assessment: AIAssessment,
    img: Image.Image,
) -> list[Detection]:
    """Convert normalized 0-1000 Gemini boxes to pixel Detections."""
    w, h = img.size
    detections: list[Detection] = []
    boxes = assessment.boxes or []

    for b in boxes:
        if len(b.box_2d) == 4:
            ymin, xmin, ymax, xmax = b.box_2d
            x1 = int(xmin * w / 1000)
            y1 = int(ymin * h / 1000)
            x2 = int(xmax * w / 1000)
            y2 = int(ymax * h / 1000)
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            area_ratio = max(((x2 - x1) * (y2 - y1)) / (w * h), 0.001)
            cls_name = b.label if b.label in ISSUE_CLASSES else assessment.hazard_type.value
            if cls_name == "none":
                cls_name = "road_damage"
            detections.append(Detection(
                class_name=cls_name,
                confidence=None,
                box=(x1, y1, x2, y2),
                area_ratio=area_ratio,
                source="gemini",
                confidence_source="gemini_estimate",
            ))

    # If confirmed but no box coordinates returned, create a central representative box
    if not detections and assessment.confirmed and assessment.hazard_type.value != "none":
        cx1, cy1 = int(w * 0.25), int(h * 0.25)
        cx2, cy2 = int(w * 0.75), int(h * 0.75)
        detections.append(Detection(
            class_name=assessment.hazard_type.value,
            confidence=None,
            box=(cx1, cy1, cx2, cy2),
            area_ratio=0.25,
            source="gemini",
            confidence_source="gemini_estimate",
        ))

    return detections


def detect_image_pil(
    img: Image.Image,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
    mode: str | None = None,
    actor: dict | None = None,
) -> DetectionResult:
    """
    Main detection pipeline supporting 'yolo', 'gemini', and 'hybrid' modes.
    """
    active_mode = mode or DETECTOR
    assessment: AIAssessment | None = None
    detections: list[Detection] = []
    is_demo = False

    if active_mode == "gemini":
        # Gemini Only
        assessment = assess_image(img, yolo_detections=None, include_boxes=True, actor=actor)
        if assessment:
            detections = _convert_gemini_boxes_to_detections(assessment, img)
        else:
            # Fallback to YOLO/Demo if Gemini unavailable
            yolo_dets, is_demo = run_yolo_detection(img, conf_threshold, class_list)
            detections = yolo_dets

    elif active_mode == "yolo":
        # YOLO Only
        yolo_dets, is_demo = run_yolo_detection(img, conf_threshold, class_list)
        detections = yolo_dets

    else:
        # Hybrid Mode (Default)
        yolo_dets, is_demo = run_yolo_detection(img, conf_threshold, class_list)
        detections = yolo_dets

        # Check with Gemini for assessment and extra classes
        det_dicts = [d.to_dict() for d in detections]
        assessment = assess_image(img, yolo_detections=det_dicts, include_boxes=True, actor=actor)

        if assessment:
            # If YOLO found nothing or missing model, incorporate Gemini findings
            if not detections and assessment.confirmed and assessment.hazard_type.value != "none":
                detections = _convert_gemini_boxes_to_detections(assessment, img)
            elif assessment.confirmed and assessment.hazard_type.value == "streetlight":
                # Add streetlight if YOLO missed it
                has_light = any(d.class_name == "streetlight" for d in detections)
                if not has_light:
                    gemini_boxes = _convert_gemini_boxes_to_detections(assessment, img)
                    for gb in gemini_boxes:
                        if gb.class_name == "streetlight":
                            detections.append(gb)

    # Draw boxes
    annotated = _draw_boxes(img, detections)

    return DetectionResult(
        detections=detections,
        annotated_image=annotated,
        demo_mode=is_demo,
        detector_used=active_mode,
        assessment=assessment,
    )


def detect_image(
    image_path: str,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
    mode: str | None = None,
    actor: dict | None = None,
) -> DetectionResult:
    """Run detection on an image file path."""
    img = Image.open(image_path).convert("RGB")
    return detect_image_pil(img, conf_threshold, class_list, mode=mode, actor=actor)


# ─── Video detection ─────────────────────────────────────────────────────────

def detect_video(
    video_path: str,
    sample_fps: int = 1,
    conf_threshold: float = 0.35,
    class_list: list[str] | None = None,
    mode: str | None = None,
    actor: dict | None = None,
) -> list[DetectionResult]:
    """
    Sample 1 frame per second from a video, run hybrid detection,
    and return the best detection result per distinct hazard.
    """
    try:
        import cv2  # noqa: PLC0415
    except ImportError:
        return []

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(int(fps / sample_fps), 1)

    results: list[DetectionResult] = []
    best_per_class: dict[str, tuple[float, DetectionResult]] = {}
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            res = detect_image_pil(pil_img, conf_threshold, class_list, mode=mode, actor=actor)

            if res.detections:
                for det in res.detections:
                    conf = det.confidence if det.confidence is not None else GEMINI_DEFAULT_CONFIDENCE
                    if det.class_name not in best_per_class or conf > best_per_class[det.class_name][0]:
                        best_per_class[det.class_name] = (conf, res)

        frame_idx += 1
        if frame_idx > 300:  # limit to ~10-second clips at 30 fps
            break

    cap.release()
    return [item[1] for item in best_per_class.values()]


# ─── Demo detections generator ───────────────────────────────────────────────

def _demo_detections_list(img: Image.Image, class_list: list[str] | None) -> list[Detection]:
    allowed = class_list or ISSUE_CLASSES
    w, h = img.size
    class_name = random.choice(allowed)
    conf = round(random.uniform(0.70, 0.96), 2)
    x1 = int(w * random.uniform(0.15, 0.30))
    y1 = int(h * random.uniform(0.20, 0.40))
    x2 = int(w * random.uniform(0.65, 0.85))
    y2 = int(h * random.uniform(0.60, 0.80))
    area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
    return [Detection(
        class_name=class_name,
        confidence=conf,
        box=(x1, y1, x2, y2),
        area_ratio=area_ratio,
        source="yolo",
        confidence_source="measured",
    )]


# ─── Annotation renderer ─────────────────────────────────────────────────────

def _draw_boxes(img: Image.Image, detections: list[Detection]) -> Image.Image:
    """Draw bounding boxes and class pills on a copy of the image."""
    annotated = img.copy()
    draw = ImageDraw.Draw(annotated)
    try:
        font = ImageFont.load_default(size=14)
    except Exception:
        font = ImageFont.load_default()

    for det in detections:
        color = _BOX_COLORS.get(det.class_name, _DEFAULT_COLOR)
        x1, y1, x2, y2 = det.box

        # Box outline
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # Label pill text
        if det.confidence is not None:
            text = f"{det.class_name} {det.confidence:.0%}"
        else:
            text = f"{det.class_name} (est)"

        if det.source == "gemini":
            text += " [Gemini]"

        try:
            bbox = font.getbbox(text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * 7, 14

        draw.rectangle([x1, y1 - th - 6, x1 + tw + 8, y1], fill=color)
        draw.text((x1 + 4, y1 - th - 4), text, fill="white", font=font)

    return annotated
