"""
Database layer for UrbanLens.
All reads/writes go through this module; permission checks are enforced here.
Uses parameterized queries only; never formats user data into SQL strings.
"""

from __future__ import annotations

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from core.config import DB_PATH

# ─── Permission matrix ────────────────────────────────────────────────────────
_PERMISSIONS: dict[str, set[str]] = {
    "admin":   {
        "view_public_map", "upload_report", "view_queue", "assign_status",
        "view_analytics", "view_audit", "manage_users", "export_csv",
        "view_own_reports", "view_issue_detail", "add_comment", "manage_credits",
    },
    "officer": {
        "view_public_map", "upload_report", "view_queue", "assign_status",
        "view_analytics", "export_csv", "view_own_reports",
        "view_issue_detail", "add_comment", "verify_report",
    },
    "citizen": {
        "view_public_map", "upload_report", "view_own_reports",
        "view_issue_detail", "add_comment", "view_leaderboard",
    },
    "guest":   {"view_public_map"},
}


def require_permission(user: dict | None, action: str) -> None:
    """Raise PermissionError and log if user lacks the permission."""
    role = (user or {}).get("role", "guest")
    if action not in _PERMISSIONS.get(role, set()):
        username = (user or {}).get("username", "anonymous")
        # Log denied attempt (import here to avoid circular)
        try:
            from core.audit import log_audit  # noqa: PLC0415
            log_audit(username, role, "denied", None, f"Attempted: {action}")
        except Exception:
            pass
        raise PermissionError(
            f"Role '{role}' is not permitted to perform '{action}'."
        )


def has_permission(user: dict | None, action: str) -> bool:
    """Return True if user has the permission (no raise)."""
    role = (user or {}).get("role", "guest")
    return action in _PERMISSIONS.get(role, set())


# ─── Connection ───────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables and indexes if they do not exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            name        TEXT    NOT NULL,
            password_hash TEXT  NOT NULL,
            role        TEXT    NOT NULL DEFAULT 'citizen',
            active      INTEGER NOT NULL DEFAULT 1,
            show_on_leaderboard INTEGER NOT NULL DEFAULT 1,
            strikes     INTEGER NOT NULL DEFAULT 0,
            rewards_suspended INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS issues (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            type            TEXT    NOT NULL,
            severity_score  REAL    NOT NULL DEFAULT 0,
            severity_label  TEXT    NOT NULL DEFAULT 'Low',
            priority        REAL    NOT NULL DEFAULT 0,
            lat             REAL,
            lon             REAL,
            area            TEXT    DEFAULT '',
            location_type   TEXT    DEFAULT 'default',
            image_path      TEXT    DEFAULT '',
            report_count    INTEGER NOT NULL DEFAULT 1,
            status          TEXT    NOT NULL DEFAULT 'reported',
            assigned_to     TEXT    DEFAULT NULL,
            reported_by     TEXT    NOT NULL DEFAULT '',
            ai_assessment   TEXT    DEFAULT NULL,
            ai_model        TEXT    DEFAULT NULL,
            detector_source TEXT    DEFAULT 'yolo',
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            verified_by     TEXT    DEFAULT NULL,
            verified_at     TEXT    DEFAULT NULL,
            reject_reason   TEXT    DEFAULT NULL,
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS issue_images (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    INTEGER NOT NULL REFERENCES issues(id),
            image_path  TEXT    NOT NULL,
            confidence  REAL    NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id    INTEGER NOT NULL REFERENCES issues(id),
            user        TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            text        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user        TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            action      TEXT    NOT NULL,
            issue_id    INTEGER DEFAULT NULL,
            detail      TEXT    DEFAULT '',
            timestamp   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS credit_ledger (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            delta       INTEGER NOT NULL,
            reason_code TEXT    NOT NULL,
            issue_id    INTEGER REFERENCES issues(id),
            note        TEXT    DEFAULT '',
            created_by  TEXT    NOT NULL DEFAULT 'system',
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            badge_key   TEXT    NOT NULL,
            awarded_at  TEXT    NOT NULL,
            metadata    TEXT    DEFAULT '{}',
            UNIQUE(user_id, badge_key)
        );

        CREATE TABLE IF NOT EXISTS gemini_cache (
            cache_key   TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            feature     TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS geo_cache (
            cache_key   TEXT PRIMARY KEY,
            area_name   TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_issues_status       ON issues(status);
        CREATE INDEX IF NOT EXISTS idx_issues_severity     ON issues(severity_label);
        CREATE INDEX IF NOT EXISTS idx_issues_type         ON issues(type);
        CREATE INDEX IF NOT EXISTS idx_issues_created      ON issues(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp     ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_user          ON audit_log(user);
        CREATE INDEX IF NOT EXISTS idx_credit_user         ON credit_ledger(user_id);
        CREATE INDEX IF NOT EXISTS idx_credit_created      ON credit_ledger(created_at);
        CREATE INDEX IF NOT EXISTS idx_badges_user         ON badges(user_id);
        """)

        # Schema migrations for existing DB
        issue_cols = [r["name"] for r in conn.execute("PRAGMA table_info(issues)").fetchall()]
        if "ai_assessment" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN ai_assessment TEXT DEFAULT NULL")
        if "ai_model" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN ai_model TEXT DEFAULT NULL")
        if "detector_source" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN detector_source TEXT DEFAULT 'yolo'")
        if "verification_status" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'unverified'")
        if "verified_by" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN verified_by TEXT DEFAULT NULL")
        if "verified_at" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN verified_at TEXT DEFAULT NULL")
        if "reject_reason" not in issue_cols:
            conn.execute("ALTER TABLE issues ADD COLUMN reject_reason TEXT DEFAULT NULL")

        user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "show_on_leaderboard" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN show_on_leaderboard INTEGER NOT NULL DEFAULT 1")
        if "strikes" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN strikes INTEGER NOT NULL DEFAULT 0")
        if "rewards_suspended" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN rewards_suspended INTEGER NOT NULL DEFAULT 0")

        # Now safe to create index on migration column
        conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_verification ON issues(verification_status)")


def db_is_empty() -> bool:
    """Return True if no users exist (DB needs seeding)."""
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()
        return row["n"] == 0


# ─── User helpers ─────────────────────────────────────────────────────────────

def get_user(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(uid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=? AND active=1", (uid,)
        ).fetchone()
        return dict(row) if row else None


def update_user_privacy(user_id: int, show_on_leaderboard: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET show_on_leaderboard=? WHERE id=?",
            (1 if show_on_leaderboard else 0, user_id),
        )


def update_user_strikes(actor: dict, user_id: int, strikes: int, rewards_suspended: bool) -> None:
    if not (has_permission(actor, "manage_users") or has_permission(actor, "verify_report")):
        raise PermissionError("Not authorized to update user strikes.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET strikes=?, rewards_suspended=? WHERE id=?",
            (strikes, 1 if rewards_suspended else 0, user_id),
        )


def create_user(
    actor: dict, username: str, name: str,
    password_hash: str, role: str
) -> int:
    require_permission(actor, "manage_users")
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username,name,password_hash,role,active,show_on_leaderboard,strikes,rewards_suspended,created_at)"
            " VALUES (?,?,?,?,1,1,0,0,?)",
            (username, name, password_hash, role, now),
        )
        return cur.lastrowid


def list_users(actor: dict) -> list[dict]:
    require_permission(actor, "manage_users")
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def update_user_role(actor: dict, uid: int, new_role: str) -> None:
    require_permission(actor, "manage_users")
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role=? WHERE id=?", (new_role, uid)
        )


def deactivate_user(actor: dict, uid: int) -> None:
    require_permission(actor, "manage_users")
    with get_conn() as conn:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (uid,))


# ─── Issue helpers ────────────────────────────────────────────────────────────

def create_issue(actor: dict, data: dict) -> int:
    require_permission(actor, "upload_report")
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO issues
               (type,severity_score,severity_label,priority,lat,lon,area,
                location_type,image_path,report_count,status,assigned_to,
                reported_by,ai_assessment,ai_model,detector_source,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data["type"], data["severity_score"], data["severity_label"],
                data["priority"], data.get("lat"), data.get("lon"),
                data.get("area", ""), data.get("location_type", "default"),
                data.get("image_path", ""), data.get("report_count", 1),
                data.get("status", "reported"), data.get("assigned_to"),
                actor.get("username", ""), data.get("ai_assessment"),
                data.get("ai_model"), data.get("detector_source", "yolo"),
                now, now,
            ),
        )
        iid = cur.lastrowid

    if data.get("image_path"):
        add_issue_image(
            iid, data["image_path"],
            data.get("confidence", 0.0) or 0.0
        )
    return iid


def get_issue(issue_id: int, actor: dict | None = None) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM issues WHERE id=?", (issue_id,)
        ).fetchone()
        if not row:
            return None
        issue = dict(row)

    # Citizens may only view their own issues
    if actor and actor.get("role") == "citizen":
        if issue.get("reported_by") != actor.get("username"):
            return None
    return issue


def list_issues(
    actor: dict | None,
    filters: dict | None = None,
) -> list[dict]:
    """Return issues respecting role. Filters: type, severity_label, status, area, date_from, date_to."""
    role = (actor or {}).get("role", "guest")
    clauses: list[str] = []
    params: list[Any] = []

    if role == "citizen":
        clauses.append("reported_by=?")
        params.append(actor["username"])

    f = filters or {}
    if f.get("type"):
        placeholders = ",".join("?" * len(f["type"]))
        clauses.append(f"type IN ({placeholders})")
        params.extend(f["type"])
    if f.get("severity_label"):
        placeholders = ",".join("?" * len(f["severity_label"]))
        clauses.append(f"severity_label IN ({placeholders})")
        params.extend(f["severity_label"])
    if f.get("status"):
        placeholders = ",".join("?" * len(f["status"]))
        clauses.append(f"status IN ({placeholders})")
        params.extend(f["status"])
    if f.get("area"):
        clauses.append("area LIKE ?")
        params.append(f"%{f['area']}%")
    if f.get("date_from"):
        clauses.append("created_at >= ?")
        params.append(f["date_from"])
    if f.get("date_to"):
        clauses.append("created_at <= ?")
        params.append(f["date_to"])
    if f.get("assigned_to"):
        clauses.append("assigned_to=?")
        params.append(f["assigned_to"])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM issues {where} ORDER BY priority DESC, created_at DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_map_issues(actor: dict | None, filters: dict | None = None) -> list[dict]:
    """
    Fetch issues for map display with backend-enforced RBAC field filtering.
    Guest & Citizen users receive public operational fields only (no reporter or assignee info).
    """
    require_permission(actor, "view_public_map")
    role = (actor or {}).get("role", "guest")

    raw_issues = list_issues(actor=actor if role in ["admin", "officer"] else None, filters=filters)
    # Filter to only issues with valid geographical coordinates
    geo_issues = [i for i in raw_issues if i.get("lat") is not None and i.get("lon") is not None]

    if role in ["admin", "officer"]:
        return geo_issues

    # Redact sensitive fields for Citizen and Guest roles
    sanitized: list[dict] = []
    for item in geo_issues:
        sanitized.append({
            "id": item["id"],
            "type": item["type"],
            "severity_score": item["severity_score"],
            "severity_label": item["severity_label"],
            "priority": item["priority"],
            "lat": item["lat"],
            "lon": item["lon"],
            "area": item.get("area", ""),
            "location_type": item.get("location_type", "default"),
            "image_path": item.get("image_path", ""),
            "report_count": item.get("report_count", 1),
            "status": item["status"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            # Redacted fields
            "reported_by": None,
            "assigned_to": None,
            "ai_assessment": item.get("ai_assessment"),
        })
    return sanitized


def update_issue_status(actor: dict, issue_id: int, new_status: str, assigned_to: str | None = None) -> None:
    require_permission(actor, "assign_status")
    now = _now()
    with get_conn() as conn:
        if assigned_to is not None:
            conn.execute(
                "UPDATE issues SET status=?, assigned_to=?, updated_at=? WHERE id=?",
                (new_status, assigned_to, now, issue_id),
            )
        else:
            conn.execute(
                "UPDATE issues SET status=?, updated_at=? WHERE id=?",
                (new_status, now, issue_id),
            )


def increment_report_count(issue_id: int, new_image_path: str, confidence: float) -> None:
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "UPDATE issues SET report_count=report_count+1, updated_at=? WHERE id=?",
            (now, issue_id),
        )
    add_issue_image(issue_id, new_image_path, confidence)


def add_issue_image(issue_id: int, image_path: str, confidence: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO issue_images (issue_id,image_path,confidence,created_at) VALUES (?,?,?,?)",
            (issue_id, image_path, confidence, _now()),
        )


def get_issue_images(issue_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM issue_images WHERE issue_id=? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Comments ─────────────────────────────────────────────────────────────────

def add_comment(actor: dict, issue_id: int, text: str) -> None:
    require_permission(actor, "add_comment")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO comments (issue_id,user,role,text,created_at) VALUES (?,?,?,?,?)",
            (issue_id, actor["username"], actor["role"], text, _now()),
        )


def get_comments(issue_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM comments WHERE issue_id=? ORDER BY created_at",
            (issue_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Audit log ────────────────────────────────────────────────────────────────

def write_audit(user: str, role: str, action: str, issue_id: int | None, detail: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user,role,action,issue_id,detail,timestamp) VALUES (?,?,?,?,?,?)",
            (user, role, action, issue_id, detail, _now()),
        )


def get_audit_log(actor: dict, filters: dict | None = None, limit: int = 500) -> list[dict]:
    require_permission(actor, "view_audit")
    f = filters or {}
    clauses: list[str] = []
    params: list[Any] = []
    if f.get("user"):
        clauses.append("user=?")
        params.append(f["user"])
    if f.get("action"):
        clauses.append("action=?")
        params.append(f["action"])
    if f.get("issue_id"):
        clauses.append("issue_id=?")
        params.append(f["issue_id"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_issue_audit(issue_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE issue_id=? ORDER BY timestamp",
            (issue_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── KPI helpers ──────────────────────────────────────────────────────────────

def kpi_counts(actor: dict | None) -> dict:
    role = (actor or {}).get("role", "guest")
    with get_conn() as conn:
        if role == "citizen":
            u = actor["username"]
            total = conn.execute("SELECT COUNT(*) FROM issues WHERE reported_by=?", (u,)).fetchone()[0]
            high  = conn.execute("SELECT COUNT(*) FROM issues WHERE reported_by=? AND severity_label='High'", (u,)).fetchone()[0]
            fixed_week = conn.execute(
                "SELECT COUNT(*) FROM issues WHERE reported_by=? AND status='fixed'"
                " AND updated_at >= datetime('now','-7 days')", (u,)
            ).fetchone()[0]
            avg_fix = conn.execute(
                "SELECT AVG((julianday(updated_at)-julianday(created_at))*24)"
                " FROM issues WHERE reported_by=? AND status='fixed'", (u,)
            ).fetchone()[0]
        else:
            total = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
            high  = conn.execute("SELECT COUNT(*) FROM issues WHERE severity_label='High'").fetchone()[0]
            fixed_week = conn.execute(
                "SELECT COUNT(*) FROM issues WHERE status='fixed'"
                " AND updated_at >= datetime('now','-7 days')"
            ).fetchone()[0]
            avg_fix = conn.execute(
                "SELECT AVG((julianday(updated_at)-julianday(created_at))*24)"
                " FROM issues WHERE status='fixed'"
            ).fetchone()[0]
    return {
        "total": total,
        "high": high,
        "fixed_week": fixed_week,
        "avg_fix_hours": round(avg_fix, 1) if avg_fix else 0,
    }


def sparkline_data(days: int = 14) -> list[int]:
    """Return daily issue counts for the last N days."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date(created_at) as d, COUNT(*) as n
               FROM issues
               WHERE created_at >= datetime('now', ?)
               GROUP BY d ORDER BY d""",
            (f"-{days} days",),
        ).fetchall()
    counts = {r["d"]: r["n"] for r in rows}
    from datetime import date, timedelta
    today = date.today()
    return [counts.get(str(today - timedelta(days=i)), 0) for i in range(days - 1, -1, -1)]


# ─── Verification & Credits helpers ──────────────────────────────────────────

def verify_issue_db(actor: dict, issue_id: int) -> dict:
    """Verify an issue in the database. Checks permissions and self-verification."""
    require_permission(actor, "verify_report")
    actor_user = actor.get("username", "")
    now = _now()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not row:
            raise ValueError(f"Issue #{issue_id} not found.")
        issue = dict(row)
        if issue.get("reported_by") == actor_user:
            raise ValueError("Officers cannot verify their own reports.")
        conn.execute(
            "UPDATE issues SET verification_status='verified', verified_by=?, verified_at=?, reject_reason=NULL, updated_at=? WHERE id=?",
            (actor_user, now, now, issue_id),
        )
        updated = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        return dict(updated)


def reject_issue_db(actor: dict, issue_id: int, reason: str) -> dict:
    """Reject an issue with a required reason."""
    require_permission(actor, "verify_report")
    if not reason or not reason.strip():
        raise ValueError("A reason is required when rejecting a report.")
    actor_user = actor.get("username", "")
    now = _now()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not row:
            raise ValueError(f"Issue #{issue_id} not found.")
        conn.execute(
            "UPDATE issues SET verification_status='rejected', verified_by=?, verified_at=?, reject_reason=?, updated_at=? WHERE id=?",
            (actor_user, now, reason.strip(), now, issue_id),
        )
        updated = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        return dict(updated)


def add_credit_ledger_entry(
    user_id: int, delta: int, reason_code: str,
    issue_id: int | None = None, note: str = "",
    created_by: str = "system"
) -> int:
    """Insert an append-only transaction into credit_ledger."""
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO credit_ledger (user_id, delta, reason_code, issue_id, note, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, delta, reason_code, issue_id, note, created_by, now),
        )
        return cur.lastrowid


def get_user_credits_balance(user_id: int) -> int:
    """Return current net credits for user."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(delta), 0) as balance FROM credit_ledger WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return int(row["balance"]) if row else 0


def get_user_credit_ledger(user_id: int, limit: int = 50) -> list[dict]:
    """Return transaction history for user."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM credit_ledger WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_daily_credits_count(user_id: int, date_str: str | None = None) -> int:
    """Return count of verified report rewards earned on given date (default today)."""
    with get_conn() as conn:
        target_date = date_str or "now"
        clause = "date(created_at) = date('now')" if not date_str else "date(created_at) = date(?)"
        params = [user_id] if not date_str else [user_id, date_str]
        row = conn.execute(
            f"SELECT COUNT(*) as n FROM credit_ledger WHERE user_id=? AND delta > 0 AND reason_code='REPORT_VERIFIED' AND {clause}",
            params,
        ).fetchone()
        return int(row["n"]) if row else 0


def award_badge_db(user_id: int, badge_key: str, metadata_json: str = "{}") -> bool:
    """Insert badge if not already awarded. Return True if new badge added."""
    now = _now()
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO badges (user_id, badge_key, awarded_at, metadata) VALUES (?, ?, ?, ?)",
                (user_id, badge_key, now, metadata_json),
            )
            return conn.total_changes > 0
        except Exception:
            return False


def get_user_badges(user_id: int) -> list[dict]:
    """Return all awarded badges for user."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM badges WHERE user_id=? ORDER BY awarded_at ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_verified_reports_count(username: str) -> int:
    """Return total number of verified reports submitted by user."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM issues WHERE reported_by=? AND verification_status='verified'",
            (username,),
        ).fetchone()
        return int(row["n"]) if row else 0


def get_leaderboard_data(period: str = "all_time") -> list[dict]:
    """
    Return sorted leaderboard ranking for active citizens who have not opted out.
    Period can be 'this_week', 'this_month', 'all_time'.
    """
    date_clause = ""
    if period == "this_week":
        date_clause = "AND cl.created_at >= datetime('now', '-7 days')"
    elif period == "this_month":
        date_clause = "AND cl.created_at >= datetime('now', '-30 days')"

    with get_conn() as conn:
        query = f"""
        SELECT 
            u.id as user_id,
            u.username,
            u.name,
            u.show_on_leaderboard,
            u.strikes,
            u.rewards_suspended,
            COALESCE(SUM(CASE WHEN cl.delta > 0 THEN cl.delta ELSE 0 END), 0) as period_credits,
            (SELECT COALESCE(SUM(delta), 0) FROM credit_ledger WHERE user_id = u.id) as total_credits,
            (SELECT COUNT(*) FROM issues WHERE reported_by = u.username AND verification_status = 'verified') as verified_reports
        FROM users u
        LEFT JOIN credit_ledger cl ON u.id = cl.user_id {date_clause}
        WHERE u.role = 'citizen' AND u.active = 1
        GROUP BY u.id
        ORDER BY period_credits DESC, total_credits DESC, verified_reports DESC, u.created_at ASC
        """
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]


# ─── Utility ──────────────────────────────────────────────────────────────────

def _now() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

