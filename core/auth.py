"""
Authentication: login, session management, role helpers.
Passwords hashed with bcrypt.
"""

from __future__ import annotations

import bcrypt
import streamlit as st

from core.db import get_user, has_permission
from core.audit import log_audit


# ─── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ─── Login ────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> tuple[bool, str]:
    """Attempt login. Returns (success, message)."""
    user = get_user(username.strip())
    if not user:
        log_audit(username, "unknown", "login_failed", None, "User not found")
        return False, "Invalid username or password."
    if not check_password(password, user["password_hash"]):
        log_audit(username, user["role"], "login_failed", None, "Wrong password")
        return False, "Invalid username or password."
    st.session_state["user"] = {
        "id":       user["id"],
        "username": user["username"],
        "name":     user["name"],
        "role":     user["role"],
    }
    log_audit(user["username"], user["role"], "login", None, "Login successful")
    return True, f"Welcome, {user['name']}!"


def continue_as_guest() -> None:
    st.session_state["user"] = {
        "id": None, "username": "guest", "name": "Guest", "role": "guest"
    }


def logout() -> None:
    user = st.session_state.get("user", {})
    log_audit(user.get("username", "guest"), user.get("role", "guest"), "logout", None, "")
    for key in ["user", "filters"]:
        st.session_state.pop(key, None)


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_role(roles: list[str]) -> None:
    """Stop page execution if the current user's role is not in `roles`."""
    user = current_user()
    role = (user or {}).get("role", "guest")
    if role not in roles:
        st.error(
            "You do not have permission to view this page. "
            "Please contact your administrator."
        )
        st.stop()


def is_authenticated() -> bool:
    return current_user() is not None
