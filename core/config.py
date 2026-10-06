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

# ─── Citizen Credits & Rewards Rules ──────────────────────────────────────────
CREDIT_RULES: dict[str, int] = {
    "report_verified":       10,  # Base credit when Officer verifies a report
    "first_at_location":      5,  # Bonus: first verified report at that spot (not duplicate)
    "high_severity_bonus":   10,  # Bonus: verified High-severity hazard
    "gps_and_ai_confidence":  3,  # Bonus: photo has GPS and AI confidence >= 0.50
    "confirm_existing_bonus": 2,  # Bonus: merged duplicate report verified
    "issue_fixed":           10,  # Credited when reported issue status changes to Fixed
    "report_rejected":      -15,  # Penalty for fake, misleading, or rejected reports
}

# Anti-abuse constraints
MAX_STRIKES_ALLOWED = 3
DAILY_CREDIT_REPORT_CAP = 5       # Max 5 credited reports per user per calendar day
DUPLICATE_REPORT_COOLDOWN_HOURS = 24

# Citizen Progression Levels
CITIZEN_LEVELS: list[dict] = [
    {"level": 1, "title": "Newcomer",       "min_credits": 0},
    {"level": 2, "title": "Observer",       "min_credits": 50},
    {"level": 3, "title": "Contributor",    "min_credits": 150},
    {"level": 4, "title": "Guardian",       "min_credits": 400},
    {"level": 5, "title": "City Champion",  "min_credits": 1000},
]

# Badge definitions (no emojis in rendered UI, clean titles)
BADGE_DEFINITIONS: dict[str, dict] = {
    "first_report":        {"title": "First Report",        "description": "Submitted your first verified infrastructure hazard."},
    "verified_10":         {"title": "10 Verified Reports", "description": "10 distinct reports verified by municipal officers."},
    "pothole_spotter":     {"title": "Pothole Spotter",     "description": "Reported 5 or more verified potholes across Indore."},
    "streetlight_watcher": {"title": "Streetlight Watcher", "description": "Reported 3 or more verified broken streetlights."},
    "drain_detective":     {"title": "Drain Detective",     "description": "Reported 3 or more verified overflowing drains."},
    "fixed_it":            {"title": "Fixed It",            "description": "5 of your reported issues were resolved and closed."},
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
DEFAULT_ZOOM = 12
DEFAULT_CITY = "Indore, Madhya Pradesh"

# Map bounding box validation (Indore metropolitan region)
MAP_BOUNDS_LAT = (22.0, 23.5)
MAP_BOUNDS_LON = (75.0, 76.5)

# Map Layer & Geocoding Configuration
NOMINATIM_USER_AGENT = "UrbanLens Civic Platform (https://github.com/urvashimisal126-bot/ProjectX)"
ENABLE_SATELLITE_LAYER = True
MAP_MAX_MARKERS = 1000
WARDS_GEOJSON_PATH = "data/wards.geojson"

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


# ─── Gamification & Citizen Credits ──────────────────────────────────────────
CREDIT_RULES: dict[str, int] = {
    "REPORT_VERIFIED": 25,
    "HIGH_SEVERITY_BONUS": 15,
    "FIRST_REPORT_BONUS": 50,
    "PHOTO_QUALITY_BONUS": 10,
    "DUPLICATE_MERGED": 5,
    "PENALTY_SPAM": -50,
}

CITIZEN_LEVELS: list[dict] = [
    {"level": 1, "title": "Neighbourhood Watch", "min_credits": 0, "max_credits": 99},
    {"level": 2, "title": "Civic Scout", "min_credits": 100, "max_credits": 249},
    {"level": 3, "title": "Community Champion", "min_credits": 250, "max_credits": 499},
    {"level": 4, "title": "City Guardian", "min_credits": 500, "max_credits": 999},
    {"level": 5, "title": "Civic Legend", "min_credits": 1000, "max_credits": 999999},
]

BADGE_DEFINITIONS: dict[str, dict] = {
    "FIRST_STEP": {
        "title": "First Step",
        "description": "Submitted first verified civic issue.",
        "icon": "flag",
    },
    "ROAD_WARRIOR": {
        "title": "Road Warrior",
        "description": "5+ verified road & pothole reports.",
        "icon": "directions_car",
    },
    "COMMUNITY_HERO": {
        "title": "Community Hero",
        "description": "10+ verified reports across the city.",
        "icon": "military_tech",
    },
    "CENTURION": {
        "title": "Centurion",
        "description": "Accumulated over 100 civic credits.",
        "icon": "workspace_premium",
    },
    "MASTER_GUARDIAN": {
        "title": "Master Guardian",
        "description": "Reached Citizen Level 4 (City Guardian).",
        "icon": "shield",
    },
}

DAILY_CREDIT_REPORT_CAP: int = 5
MAX_STRIKES_ALLOWED: int = 3
DUPLICATE_REPORT_COOLDOWN_HOURS: int = 24



