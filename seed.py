"""
Seed script: creates DB schema, demo users, and ~30 realistic issues around Indore.
Idempotent — safe to run multiple times.
"""

from __future__ import annotations

import os
import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from core.config import DB_PATH, UPLOAD_DIR, SAMPLE_DIR, ISSUE_CLASSES, INDORE_AREAS, ISSUE_LABELS
from core.db import init_db, get_conn, db_is_empty
from core.auth import hash_password
from core.audit import log_audit

# ─── Demo users ──────────────────────────────────────────────────────────────
DEMO_USERS = [
    ("admin",    "Admin User",    "admin123",   "admin"),
    ("officer1", "Ravi Sharma",   "officer123", "officer"),
    ("officer2", "Priya Patel",   "officer123", "officer"),
    ("citizen1", "Ankit Joshi",   "citizen123", "citizen"),
]

# ─── Indore coordinates (area → approx centre) ───────────────────────────────
AREA_COORDS = {
    "Vijay Nagar":        (22.7448, 75.9090),
    "Palasia":            (22.7268, 75.8636),
    "Rajwada":            (22.7180, 75.8580),
    "Bhawarkuan":         (22.7020, 75.8800),
    "Rau":                (22.6330, 75.8100),
    "Sudama Nagar":       (22.6890, 75.8850),
    "Scheme 54":          (22.7540, 75.9010),
    "Scheme 78":          (22.7400, 75.8820),
    "Geeta Bhawan":       (22.7200, 75.8750),
    "Annapurna":          (22.6980, 75.8700),
    "LIG Colony":         (22.7080, 75.8650),
    "Nipania":            (22.7480, 75.9210),
    "Near AITR":          (22.6761, 75.8746),
    "MG Road":            (22.7200, 75.8800),
    "Khajrana":           (22.7060, 75.9080),
}


def _jitter(lat: float, lon: float, metres: float = 300) -> tuple[float, float]:
    deg = metres / 111_000
    return lat + random.uniform(-deg, deg), lon + random.uniform(-deg, deg)


def _rand_ts(days_ago_max: int = 30, days_ago_min: int = 0) -> str:
    delta = timedelta(
        days=random.randint(days_ago_min, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%d %H:%M:%S")


def _make_placeholder_image(label: str, severity: str) -> str:
    """Create a placeholder annotated image and return the saved path."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    colors = {"High": (200, 55, 45), "Medium": (224, 138, 30), "Low": (46, 158, 107)}
    box_color = colors.get(severity, (100, 100, 200))

    img = Image.new("RGB", (640, 480), color=(230, 230, 230))
    draw = ImageDraw.Draw(img)

    # Draw texture lines
    for y in range(0, 480, 20):
        draw.line([(0, y), (640, y)], fill=(210, 210, 210), width=1)

    # Draw detection box
    bx1 = random.randint(80, 200)
    by1 = random.randint(80, 160)
    bx2 = random.randint(380, 520)
    by2 = random.randint(280, 380)
    draw.rectangle([bx1, by1, bx2, by2], outline=box_color, width=4)
    try:
        font = ImageFont.load_default(size=16)
    except Exception:
        font = ImageFont.load_default()
    draw.rectangle([bx1, by1 - 22, bx1 + len(label) * 9 + 4, by1], fill=box_color)
    draw.text((bx1 + 2, by1 - 20), label, fill="white", font=font)

    fname = f"sample_{label.replace(' ', '_')}_{random.randint(1000,9999)}.jpg"
    fpath = os.path.join(SAMPLE_DIR, fname)
    img.save(fpath, "JPEG", quality=85)
    return fpath


def seed() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    init_db()

    if not db_is_empty():
        print("DB already seeded — skipping.")
        return

    print("Seeding database …")

    # ── Users ──────────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        for username, name, password, role in DEMO_USERS:
            conn.execute(
                "INSERT OR IGNORE INTO users (username,name,password_hash,role,active,created_at)"
                " VALUES (?,?,?,?,1,?)",
                (username, name, hash_password(password), role, now),
            )
    print(f"  Created {len(DEMO_USERS)} demo users.")

    # ── Issues ─────────────────────────────────────────────────────────────
    statuses        = ["reported", "assigned", "fixed"]
    status_weights  = [0.35, 0.40, 0.25]
    severity_labels = ["Low", "Medium", "High"]
    sev_weights     = [0.30, 0.45, 0.25]
    areas           = list(AREA_COORDS.keys())
    reporters       = ["citizen1", "officer1", "admin"]
    officers        = ["officer1", "officer2"]

    issue_ids = []
    for i in range(30):
        cls = random.choice(ISSUE_CLASSES)
        sev = random.choices(severity_labels, weights=sev_weights)[0]
        status = random.choices(statuses, weights=status_weights)[0]
        area = random.choice(areas)
        base_lat, base_lon = AREA_COORDS[area]
        lat, lon = _jitter(base_lat, base_lon)
        reporter = random.choice(reporters)
        assigned = random.choice(officers) if status in ("assigned", "fixed") else None
        created = _rand_ts(30, 1)

        if status == "fixed":
            updated = (
                datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                + timedelta(hours=random.randint(4, 72))
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            updated = created

        sev_score_map = {"Low": round(random.uniform(0.10, 0.34), 3),
                         "Medium": round(random.uniform(0.35, 0.65), 3),
                         "High": round(random.uniform(0.66, 0.95), 3)}
        sev_score = sev_score_map[sev]
        priority = round(sev_score * random.uniform(1.0, 1.5), 3)
        report_count = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        img_path = _make_placeholder_image(ISSUE_LABELS[cls], sev)

        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO issues
                   (type,severity_score,severity_label,priority,lat,lon,area,
                    location_type,image_path,report_count,status,assigned_to,
                    reported_by,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cls, sev_score, sev, priority, lat, lon, area, "default",
                 img_path, report_count, status, assigned, reporter, created, updated),
            )
            iid = cur.lastrowid
        issue_ids.append(iid)

        # Audit trail
        log_audit(reporter, "citizen", "upload", iid, f"Reported {cls} in {area}")
        if status in ("assigned", "fixed"):
            log_audit(assigned or "officer1", "officer", "assigned", iid, f"Assigned to {assigned}")
        if status == "fixed":
            log_audit(assigned or "officer1", "officer", "fixed", iid, "Marked as fixed")

        # Add extra images for high-count issues
        if report_count > 1:
            extra = _make_placeholder_image(ISSUE_LABELS[cls], sev)
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO issue_images (issue_id,image_path,confidence,created_at) VALUES (?,?,?,?)",
                    (iid, extra, round(random.uniform(0.6, 0.9), 2), created),
                )

    print(f"  Created {len(issue_ids)} issues with audit history.")

    # ── Demo duplicate (merge scenario) ────────────────────────────────────
    first_id = issue_ids[0]
    with get_conn() as conn:
        conn.execute(
            "UPDATE issues SET report_count=2 WHERE id=?", (first_id,)
        )
    log_audit("citizen1", "citizen", "merged", first_id, "Duplicate merged into issue")
    print("  Created 1 merged duplicate scenario.")

    # ── Comments ───────────────────────────────────────────────────────────
    sample_comments = [
        ("officer1", "officer", "Inspected — will dispatch crew by EOD."),
        ("admin",    "admin",   "Escalated due to proximity to school zone."),
        ("citizen1", "citizen", "This has been here for two weeks now."),
    ]
    for iid in random.sample(issue_ids, min(6, len(issue_ids))):
        comment = random.choice(sample_comments)
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO comments (issue_id,user,role,text,created_at) VALUES (?,?,?,?,?)",
                (iid, comment[0], comment[1], comment[2], _rand_ts(5)),
            )
    print("  Added sample comments.")
    print("Seeding complete.")
    print("\nDemo credentials:")
    for username, name, password, role in DEMO_USERS:
        print(f"  {role:10s}  {username:12s}  {password}")


if __name__ == "__main__":
    seed()
