"""
Deduplication: find and merge issues within DEDUPE_RADIUS_METERS of the same type.
"""

from __future__ import annotations

from core.config import DEDUPE_RADIUS_METERS
from core.geo import haversine
from core.db import get_conn, increment_report_count
from core.audit import log_audit


def find_duplicate(
    issue_type: str, lat: float | None, lon: float | None
) -> int | None:
    """
    Return the id of the nearest existing issue of the same type within
    DEDUPE_RADIUS_METERS, or None.
    """
    if lat is None or lon is None:
        return None

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, lat, lon FROM issues WHERE type=? AND lat IS NOT NULL AND lon IS NOT NULL",
            (issue_type,),
        ).fetchall()

    for row in rows:
        dist = haversine(lat, lon, row["lat"], row["lon"])
        if dist <= DEDUPE_RADIUS_METERS:
            return row["id"]
    return None


def merge_into(
    duplicate_id: int,
    new_image_path: str,
    confidence: float,
    actor: dict,
) -> None:
    """Increment the report count and attach the new image; log the merge."""
    increment_report_count(duplicate_id, new_image_path, confidence)
    log_audit(
        actor.get("username", "system"),
        actor.get("role", "system"),
        "merged",
        duplicate_id,
        f"Merged duplicate into issue #{duplicate_id}",
    )
