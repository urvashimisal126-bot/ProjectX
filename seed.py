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
    ("admin",     "Admin User",       "admin123",   "admin"),
    ("officer1",  "Ravi Sharma",      "officer123", "officer"),
    ("officer2",  "Priya Patel",      "officer123", "officer"),
    ("citizen1",  "Ankit Joshi",      "citizen123", "citizen"),
    ("citizen2",  "Kavita Verma",     "citizen123", "citizen"),
    ("citizen3",  "Rahul Jain",       "citizen123", "citizen"),
    ("citizen4",  "Sneha Rao",        "citizen123", "citizen"),
    ("citizen5",  "Aman Gupta",       "citizen123", "citizen"),
    ("citizen6",  "Pooja Nair",       "citizen123", "citizen"),
    ("citizen7",  "Vikram Chauhan",   "citizen123", "citizen"),
    ("citizen8",  "Ritu Agarwal",     "citizen123", "citizen"),
    ("citizen9",  "Deepak Sharma",    "citizen123", "citizen"),
    ("citizen10", "Meera Kulkarni",   "citizen123", "citizen"),
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


def seed(force: bool = False) -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    init_db()

    if not force and not db_is_empty():
        print("DB already seeded — verifying schema and seeding missing citizens.")
    else:
        print("Seeding database …")

    # ── Users ──────────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        for username, name, password, role in DEMO_USERS:
            conn.execute(
                "INSERT OR IGNORE INTO users (username,name,password_hash,role,active,show_on_leaderboard,strikes,rewards_suspended,created_at)"
                " VALUES (?,?,?,?,1,1,0,0,?)",
                (username, name, hash_password(password), role, now),
            )
    print(f"  Ensured {len(DEMO_USERS)} demo users exist.")

    # ── Issues ─────────────────────────────────────────────────────────────
    statuses        = ["reported", "assigned", "fixed"]
    status_weights  = [0.30, 0.40, 0.30]
    severity_labels = ["Low", "Medium", "High"]
    sev_weights     = [0.30, 0.45, 0.25]
    areas           = list(AREA_COORDS.keys())
    citizen_usernames = [u[0] for u in DEMO_USERS if u[3] == "citizen"]
    officers        = ["officer1", "officer2"]

    with get_conn() as conn:
        count_row = conn.execute("SELECT COUNT(*) as n FROM issues").fetchone()
        existing_issues = count_row["n"] if count_row else 0

    if existing_issues < 25:
        issue_ids = []
        for i in range(35):
            cls = random.choice(ISSUE_CLASSES)
            sev = random.choices(severity_labels, weights=sev_weights)[0]
            status = random.choices(statuses, weights=status_weights)[0]
            area = random.choice(areas)
            base_lat, base_lon = AREA_COORDS[area]
            lat, lon = _jitter(base_lat, base_lon)
            reporter = random.choice(citizen_usernames)
            assigned = random.choice(officers) if status in ("assigned", "fixed") else None
            created = _rand_ts(30, 1)

            # Assign verification status
            is_verified = (status in ("assigned", "fixed") or random.random() < 0.65)
            v_status = "verified" if is_verified else ("rejected" if random.random() < 0.15 else "unverified")
            v_by = random.choice(officers) if v_status != "unverified" else None
            v_at = created if v_status != "unverified" else None
            rej_reason = "Non-actionable image" if v_status == "rejected" else None

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
                        reported_by,verification_status,verified_by,verified_at,reject_reason,
                        created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cls, sev_score, sev, priority, lat, lon, area, "default",
                     img_path, report_count, status, assigned, reporter,
                     v_status, v_by, v_at, rej_reason, created, updated),
                )
                iid = cur.lastrowid
            issue_ids.append(iid)

            # Audit trail
            log_audit(reporter, "citizen", "upload", iid, f"Reported {cls} in {area}")
            if v_status == "verified":
                log_audit(v_by or "officer1", "officer", "verify_issue", iid, f"Verified report #{iid}")
            if status in ("assigned", "fixed"):
                log_audit(assigned or "officer1", "officer", "assigned", iid, f"Assigned to {assigned}")
            if status == "fixed":
                log_audit(assigned or "officer1", "officer", "fixed", iid, "Marked as fixed")

        print(f"  Created {len(issue_ids)} issues with verification statuses.")

    # ── Gamification: Seed Credit Ledgers & Badges for Citizens ────────────
    import core.credits as credits
    with get_conn() as conn:
        for username in citizen_usernames:
            user_row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not user_row:
                continue
            uid = user_row["id"]
            
            # Check existing ledger
            ledger_cnt = conn.execute("SELECT COUNT(*) as n FROM credit_ledger WHERE user_id=?", (uid,)).fetchone()["n"]
            if ledger_cnt == 0:
                # Find verified issues for this user
                v_issues = conn.execute(
                    "SELECT id, severity_label, created_at FROM issues WHERE reported_by=? AND verification_status='verified'",
                    (username,),
                ).fetchall()

                for idx, vi in enumerate(v_issues):
                    # Base reward
                    conn.execute(
                        """INSERT INTO credit_ledger (user_id, delta, reason_code, issue_id, note, created_by, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (uid, 25, "REPORT_VERIFIED", vi["id"], f"Report #{vi['id']} verified by officer", "officer1", vi["created_at"]),
                    )
                    if vi["severity_label"] == "High":
                        conn.execute(
                            """INSERT INTO credit_ledger (user_id, delta, reason_code, issue_id, note, created_by, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (uid, 15, "HIGH_SEVERITY_BONUS", vi["id"], "High severity hazard bonus", "system", vi["created_at"]),
                        )
                    if idx == 0:
                        conn.execute(
                            """INSERT INTO credit_ledger (user_id, delta, reason_code, issue_id, note, created_by, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (uid, 50, "FIRST_REPORT_BONUS", vi["id"], "Welcome bonus: First verified report!", "system", vi["created_at"]),
                        )

                # Extra bonus credits for top citizens to create a tiered leaderboard
                extra_bonuses = {
                    "citizen1": 320,  # Level 3 Community Champion
                    "citizen2": 550,  # Level 4 City Guardian
                    "citizen3": 180,  # Level 2 Civic Scout
                    "citizen4": 220,  # Level 2 Civic Scout
                    "citizen5": 90,   # Level 1 Neighbourhood Watch
                }
                if username in extra_bonuses:
                    conn.execute(
                        """INSERT INTO credit_ledger (user_id, delta, reason_code, note, created_by, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (uid, extra_bonuses[username], "COMMUNITY_CONTRIBUTION", "Historical verified civic contributions", "system", now),
                    )

                # Grant badges
                credits.evaluate_and_grant_badges(uid, username)

    print("  Ensured credit ledgers and badges populated for all citizens.")
    print("Seeding complete.\n")
    print("Demo credentials:")
    for username, name, password, role in DEMO_USERS:
        print(f"  {role:10s}  {username:12s}  {password}")


if __name__ == "__main__":
    seed()
