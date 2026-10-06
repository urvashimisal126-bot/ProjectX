"""
Geolocation helpers: EXIF GPS extraction, haversine distance, landmark proximity,
coordinate boundary validation, and rate-limited cached reverse geocoding.
"""

from __future__ import annotations

import math
import time
from typing import Tuple
from pathlib import Path
from PIL import Image, ExifTags

from core.config import (
    LANDMARKS, LANDMARK_RADIUS_METERS, DEFAULT_LAT, DEFAULT_LON,
    MAP_BOUNDS_LAT, MAP_BOUNDS_LON, NOMINATIM_USER_AGENT
)
from core.db import get_conn

_LAST_NOMINATIM_CALL = 0.0


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


# ─── Boundary Validation ──────────────────────────────────────────────────────

def validate_coordinates(lat: float, lon: float, strict_bounds: bool = False) -> bool:
    """Validate latitude and longitude ranges."""
    if lat is None or lon is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    if strict_bounds:
        min_lat, max_lat = MAP_BOUNDS_LAT
        min_lon, max_lon = MAP_BOUNDS_LON
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
    return True


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


# ─── Reverse Geocoding with SQLite Cache & Rate Limiting ──────────────────────

def _get_cached_area(lat_key: str, lon_key: str) -> str | None:
    cache_key = f"{lat_key},{lon_key}"
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT area_name FROM geo_cache WHERE cache_key=?", (cache_key,)).fetchone()
            if row:
                return row["area_name"]
    except Exception:
        pass
    return None


def _save_cached_area(lat_key: str, lon_key: str, area_name: str) -> None:
    cache_key = f"{lat_key},{lon_key}"
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO geo_cache (cache_key, area_name, created_at) VALUES (?, ?, ?)",
                (cache_key, area_name, now),
            )
    except Exception:
        pass


def reverse_geocode_area(lat: float, lon: float) -> str:
    """
    Resolve coordinates to an area name at submit time (never on map render).
    1. Check landmark proximity (<300m)
    2. Check SQLite geo_cache
    3. Nominatim reverse geocode (1 req/sec rate limit)
    4. Offline reverse_geocoder fallback
    """
    global _LAST_NOMINATIM_CALL
    if lat is None or lon is None:
        return "Unknown Area"

    # Step 1: Nearest named landmark (<300m)
    for landmark in LANDMARKS:
        if haversine(lat, lon, landmark["lat"], landmark["lon"]) <= 300:
            return landmark["name"]

    lat_key = f"{lat:.3f}"
    lon_key = f"{lon:.3f}"

    # Step 2: Cache lookup
    cached = _get_cached_area(lat_key, lon_key)
    if cached:
        return cached

    # Step 3: Nominatim reverse geocoding with strict 1 req/sec rate limiting
    try:
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_CALL
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=5)
        _LAST_NOMINATIM_CALL = time.time()

        location = geolocator.reverse((lat, lon), exactly_one=True, language="en")
        if location and location.raw.get("address"):
            addr = location.raw["address"]
            area_name = (
                addr.get("suburb")
                or addr.get("neighbourhood")
                or addr.get("residential")
                or addr.get("road")
                or addr.get("city_district")
                or addr.get("city")
                or "Indore Area"
            )
            _save_cached_area(lat_key, lon_key, area_name)
            return area_name
    except Exception:
        pass

    # Step 4: Offline reverse_geocoder fallback
    try:
        import reverse_geocoder as rg
        res = rg.search((lat, lon), verbose=False)
        if res and len(res) > 0:
            name = res[0].get("name", "Indore")
            _save_cached_area(lat_key, lon_key, name)
            return name
    except Exception:
        pass

    return "Indore, MP"
