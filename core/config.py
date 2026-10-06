"""
UrbanLens configuration: class lists, scoring weights, location multipliers,
landmark coordinates, and global thresholds.
"""

from __future__ import annotations

# ─── Issue classes ────────────────────────────────────────────────────────────
ISSUE_CLASSES: list[str] = ["pothole", "road_damage", "streetlight", "drain"]

ISSUE_LABELS: dict[str, str] = {
    "pothole":     "Pothole",
    "road_damage": "Road Damage",
    "streetlight": "Broken Streetlight",
    "drain":       "Overflowing Drain",
}

# ─── Scoring weights ──────────────────────────────────────────────────────────
WEIGHT_AREA_RATIO   = 0.5
WEIGHT_CONFIDENCE   = 0.3
WEIGHT_DETECT_COUNT = 0.2

SEVERITY_HIGH_THRESHOLD   = 0.65
SEVERITY_MEDIUM_THRESHOLD = 0.35

# ─── Deduplication ────────────────────────────────────────────────────────────
DEDUPE_RADIUS_METERS = 10.0      # merge issues within this distance

# ─── Location multipliers ─────────────────────────────────────────────────────
LOCATION_MULTIPLIERS: dict[str, float] = {
    "school":   1.5,
    "hospital": 1.5,
    "highway":  1.3,
    "default":  1.0,
}

# Landmark coords around Indore (lat, lon, type, name)
# Radius for proximity match: 200 m
LANDMARK_RADIUS_METERS = 200.0

LANDMARKS: list[dict] = [
    # Schools
    {"name": "Delhi Public School Indore",   "lat": 22.7196, "lon": 75.8577, "type": "school"},
    {"name": "Emerald Heights School",        "lat": 22.7312, "lon": 75.9014, "type": "school"},
    {"name": "AITR Campus",                   "lat": 22.6761, "lon": 75.8746, "type": "school"},
    {"name": "Choithram School",              "lat": 22.7228, "lon": 75.8697, "type": "school"},
    # Hospitals
    {"name": "MY Hospital",                   "lat": 22.7188, "lon": 75.8629, "type": "hospital"},
    {"name": "Bombay Hospital Indore",        "lat": 22.7340, "lon": 75.8721, "type": "hospital"},
    {"name": "Choithram Hospital",            "lat": 22.7215, "lon": 75.8651, "type": "hospital"},
    {"name": "Apollo Hospital",               "lat": 22.7561, "lon": 75.8941, "type": "hospital"},
    # Highways
    {"name": "Indore-Ujjain Highway NH-86",   "lat": 22.6800, "lon": 75.8200, "type": "highway"},
    {"name": "AB Road (National Highway 3)",  "lat": 22.7200, "lon": 75.8800, "type": "highway"},
    {"name": "Bypass Road Indore",            "lat": 22.6600, "lon": 75.9100, "type": "highway"},
]

# ─── Default location (Indore) ────────────────────────────────────────────────
DEFAULT_LAT = 22.7196
DEFAULT_LON = 75.8577
DEFAULT_CITY = "Indore, Madhya Pradesh"

# ─── Areas in Indore ─────────────────────────────────────────────────────────
INDORE_AREAS: list[str] = [
    "Vijay Nagar", "Palasia", "Rajwada", "Bhawarkuan",
    "Rau", "Sudama Nagar", "Scheme 54", "Scheme 78",
    "Geeta Bhawan", "Annapurna", "LIG Colony", "Nipania",
    "Pardesipura", "Lasudia", "Khajrana", "MG Road",
    "Near AITR", "Mangaliya", "Mahalakshmi Nagar",
]

# ─── Video sampling ───────────────────────────────────────────────────────────
VIDEO_SAMPLE_FPS = 1          # analyse 1 frame per second

# ─── Confidence threshold ─────────────────────────────────────────────────────
DEFAULT_CONF_THRESHOLD = 0.35

# ─── DB path ─────────────────────────────────────────────────────────────────
DB_PATH = "urbanlens.db"

# ─── Image storage ────────────────────────────────────────────────────────────
UPLOAD_DIR = "data/uploads"
SAMPLE_DIR = "data/samples"

# ─── Gemini & Hybrid Detection ───────────────────────────────────────────────
import os


def get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
DETECTOR = get_secret("DETECTOR", "gemini")  # "hybrid" | "yolo" | "gemini"
GEMINI_DEFAULT_CONFIDENCE = 0.50             # documented fallback for Gemini-estimated detections


