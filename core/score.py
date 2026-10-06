"""
Severity and priority scoring.
Deterministic formula: Gemini advises, the formula decides.
"""

from __future__ import annotations

from core.config import (
    WEIGHT_AREA_RATIO, WEIGHT_CONFIDENCE, WEIGHT_DETECT_COUNT,
    SEVERITY_HIGH_THRESHOLD, SEVERITY_MEDIUM_THRESHOLD,
    LOCATION_MULTIPLIERS, GEMINI_DEFAULT_CONFIDENCE,
)


def compute_severity(
    area_ratio: float,
    confidence: float | None,
    detect_count: int,
) -> tuple[float, str]:
    """
    Return (severity_score 0-1, label).
    area_ratio   = box_area / image_area  (already 0-1)
    confidence   = model confidence (0-1) or GEMINI_DEFAULT_CONFIDENCE if estimated
    detect_count = number of detections in this image (1+)
    """
    effective_conf = confidence if confidence is not None else GEMINI_DEFAULT_CONFIDENCE
    norm_area  = min(area_ratio * 10, 1.0)          # scale: 10% fill → score 1
    norm_count = min((detect_count - 1) / 9, 1.0)   # up to 10 detections

    score = (
        WEIGHT_AREA_RATIO   * norm_area
        + WEIGHT_CONFIDENCE   * effective_conf
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
    confidence: float | None,
    detect_count: int,
    location_type: str,
    report_count: int,
) -> dict:
    """Return a dict explaining each component, for the UI breakdown bar."""
    effective_conf = confidence if confidence is not None else GEMINI_DEFAULT_CONFIDENCE
    is_estimated = confidence is None

    norm_area  = min(area_ratio * 10, 1.0)
    norm_count = min((detect_count - 1) / 9, 1.0)
    multiplier = LOCATION_MULTIPLIERS.get(location_type, 1.0)
    score, label = compute_severity(area_ratio, effective_conf, detect_count)
    priority = compute_priority(score, location_type, report_count)

    conf_label = "Model confidence" if not is_estimated else "Estimated confidence (Gemini)"

    return {
        "components": [
            {"name": "Area coverage", "weight": WEIGHT_AREA_RATIO,   "value": norm_area,      "contribution": WEIGHT_AREA_RATIO * norm_area},
            {"name": conf_label,      "weight": WEIGHT_CONFIDENCE,   "value": effective_conf, "contribution": WEIGHT_CONFIDENCE * effective_conf},
            {"name": "Detection count","weight": WEIGHT_DETECT_COUNT, "value": norm_count,     "contribution": WEIGHT_DETECT_COUNT * norm_count},
        ],
        "severity_score": score,
        "severity_label": label,
        "location_multiplier": multiplier,
        "location_type": location_type,
        "report_count": report_count,
        "priority": priority,
        "is_confidence_estimated": is_estimated,
    }
