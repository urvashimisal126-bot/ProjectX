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
        "view_own_reports", "view_issue_detail", "add_comment",
    },
    "officer": {
        "view_public_map", "upload_report", "view_queue", "assign_status",
        "view_analytics", "export_csv", "view_own_reports",
        "view_issue_detail", "add_comment",
    },
    "citizen": {
        "view_public_map", "upload_report", "view_own_reports",
        "view_issue_detail", "add_comment",
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

        CREATE TABLE IF NOT EXISTS gemini_cache (
            cache_key   TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            feature     TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_issues_status       ON issues(status);
        CREATE INDEX IF NOT EXISTS idx_issues_severity     ON issues(severity_label);
        CREATE INDEX IF NOT EXISTS idx_issues_type         ON issues(type);
        CREATE INDEX IF NOT EXISTS idx_issues_created      ON issues(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp     ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_user          ON audit_log(user);
        """)

        # Schema migrations for existing DB
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(issues)").fetchall()]
        if "ai_assessment" not in cols:
            conn.execute("ALTER TABLE issues ADD COLUMN ai_assessment TEXT DEFAULT NULL")
        if "ai_model" not in cols:
            conn.execute("ALTER TABLE issues ADD COLUMN ai_model TEXT DEFAULT NULL")
        if "detector_source" not in cols:
            conn.execute("ALTER TABLE issues ADD COLUMN detector_source TEXT DEFAULT 'yolo'")


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


def create_user(
    actor: dict, username: str, name: str,
    password_hash: str, role: str
) -> int:
    require_permission(actor, "manage_users")
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username,name,password_hash,role,active,created_at)"
            " VALUES (?,?,?,?,1,?)",
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


# ─── Utility ──────────────────────────────────────────────────────────────────

def _now() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
