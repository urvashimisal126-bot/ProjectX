"""
Geolocation helpers: EXIF GPS extraction, haversine distance, location type lookup.
"""

from __future__ import annotations

import math
from typing import Tuple

from PIL import Image, ExifTags

from core.config import LANDMARKS, LANDMARK_RADIUS_METERS, DEFAULT_LAT, DEFAULT_LON


# ─── EXIF GPS ─────────────────────────────────────────────────────────────────

def _to_decimal(dms, ref: str) -> float:
    d, m, s = (float(x) for x in dms)
    decimal = d + m / 60 + s / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def extract_gps(image_path: str) -> tuple[float, float] | None:
    """Return (lat, lon) from EXIF data, or None if absent/unreadable."""
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if not exif_data:
            return None
        exif = {ExifTags.TAGS.get(k): v for k, v in exif_data.items()}
        gps_info = exif.get("GPSInfo")
        if not gps_info:
            return None
        gps = {ExifTags.GPSTAGS.get(k): v for k, v in gps_info.items()}
        lat = _to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        lon = _to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
        return lat, lon
    except Exception:
        return None


# ─── Haversine ────────────────────────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─── Location type lookup ─────────────────────────────────────────────────────

def get_location_type(lat: float, lon: float) -> str:
    """Return 'school', 'hospital', 'highway', or 'default' based on proximity."""
    if lat is None or lon is None:
        return "default"
    best_type = "default"
    best_dist = float("inf")
    for landmark in LANDMARKS:
        dist = haversine(lat, lon, landmark["lat"], landmark["lon"])
        if dist < best_dist:
            best_dist = dist
            best_type = landmark["type"]
    if best_dist <= LANDMARK_RADIUS_METERS:
        return best_type
    return "default"
