"""
Audit log helpers: thin wrappers over db.write_audit.
"""

from __future__ import annotations

from core.db import write_audit, get_issue_audit


def log_audit(
    username: str,
    role: str,
    action: str,
    issue_id: int | None,
    detail: str = "",
) -> None:
    """Write one audit row. Never raises."""
    try:
        write_audit(username, role, action, issue_id, detail)
    except Exception:
        pass


def issue_timeline(issue_id: int) -> list[dict]:
    """Return audit rows for an issue, ordered chronologically."""
    return get_issue_audit(issue_id)
