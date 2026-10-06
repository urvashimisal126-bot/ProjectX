"""
Severity and priority scoring.
"""

from __future__ import annotations

from core.config import (
    WEIGHT_AREA_RATIO, WEIGHT_CONFIDENCE, WEIGHT_DETECT_COUNT,
    SEVERITY_HIGH_THRESHOLD, SEVERITY_MEDIUM_THRESHOLD,
    LOCATION_MULTIPLIERS,
)


def compute_severity(
    area_ratio: float,
    confidence: float,
    detect_count: int,
) -> tuple[float, str]:
    """
    Return (severity_score 0-1, label).
    area_ratio  = box_area / image_area  (already 0-1)
    confidence  = model confidence       (0-1)
    detect_count = number of detections in this image (1+)
    """
    norm_area  = min(area_ratio * 10, 1.0)      # scale: 10 % fill → score 1
    norm_count = min((detect_count - 1) / 9, 1.0)  # up to 10 detections

    score = (
        WEIGHT_AREA_RATIO   * norm_area
        + WEIGHT_CONFIDENCE   * confidence
        + WEIGHT_DETECT_COUNT * norm_count
    )
    score = round(min(max(score, 0.0), 1.0), 4)

    if score >= SEVERITY_HIGH_THRESHOLD:
        label = "High"
    elif score >= SEVERITY_MEDIUM_THRESHOLD:
        label = "Medium"
    else:
        label = "Low"

    return score, label


def compute_priority(
    severity_score: float,
    location_type: str,
    report_count: int = 1,
) -> float:
    """Return priority score (higher = fix sooner)."""
    multiplier = LOCATION_MULTIPLIERS.get(location_type, 1.0)
    priority = severity_score * multiplier * (1 + 0.1 * (report_count - 1))
    return round(priority, 4)


def severity_breakdown(
    area_ratio: float,
    confidence: float,
    detect_count: int,
    location_type: str,
    report_count: int,
) -> dict:
    """Return a dict explaining each component, for the UI breakdown bar."""
    norm_area  = min(area_ratio * 10, 1.0)
    norm_count = min((detect_count - 1) / 9, 1.0)
    multiplier = LOCATION_MULTIPLIERS.get(location_type, 1.0)
    score, label = compute_severity(area_ratio, confidence, detect_count)
    priority = compute_priority(score, location_type, report_count)
    return {
        "components": [
            {"name": "Area coverage", "weight": WEIGHT_AREA_RATIO,   "value": norm_area,   "contribution": WEIGHT_AREA_RATIO * norm_area},
            {"name": "Model confidence","weight": WEIGHT_CONFIDENCE,  "value": confidence,  "contribution": WEIGHT_CONFIDENCE * confidence},
            {"name": "Detection count", "weight": WEIGHT_DETECT_COUNT,"value": norm_count,  "contribution": WEIGHT_DETECT_COUNT * norm_count},
        ],
        "severity_score": score,
        "severity_label": label,
        "location_multiplier": multiplier,
        "location_type": location_type,
        "report_count": report_count,
        "priority": priority,
    }
