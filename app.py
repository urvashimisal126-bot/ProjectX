"""
UrbanLens — main entry point.
Handles: CSS injection, auto-seed, login gate, role-based navigation.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="UrbanLens",
    page_icon="assets/icon.png" if Path("assets/icon.png").exists() else "🏙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bootstrap DB on first run ─────────────────────────────────────────────────
from core.db import init_db, db_is_empty  # noqa: E402

init_db()
if db_is_empty():
    from seed import seed  # noqa: E402, PLC0415
    with st.spinner("Setting up UrbanLens for the first time…"):
        seed()

# ── CSS injection ─────────────────────────────────────────────────────────────
from ui.theme import inject_css  # noqa: E402
inject_css()

# ── Auth state ────────────────────────────────────────────────────────────────
from core.auth import current_user, login, continue_as_guest, logout, is_authenticated  # noqa: E402
from ui.components import sidebar_user_block  # noqa: E402

# ── Page imports ──────────────────────────────────────────────────────────────
import pages.login as login_page  # noqa: E402
import pages.overview as overview_page  # noqa: E402
import pages.report as report_page  # noqa: E402
import pages.map as map_page  # noqa: E402
import pages.queue as queue_page  # noqa: E402
import pages.issue_detail as detail_page  # noqa: E402
import pages.analytics as analytics_page  # noqa: E402
import pages.my_reports as my_reports_page  # noqa: E402
import pages.audit_log as audit_page  # noqa: E402
import pages.users as users_page  # noqa: E402


def _role_nav(role: str) -> list[tuple[str, str, object]]:
    """Return (icon_svg, label, page_module) list for the given role."""
    all_pages = [
        ("overview",  "Overview",       overview_page),
        ("report",    "Report Issue",   report_page),
        ("map",       "Live Map",       map_page),
        ("queue",     "Repair Queue",   queue_page),
        ("detail",    "Issue Detail",   detail_page),
        ("analytics", "Analytics",      analytics_page),
        ("my",        "My Reports",     my_reports_page),
        ("audit",     "Audit Log",      audit_page),
        ("users",     "Users & Roles",  users_page),
    ]
    visible = {
        "admin":   {"overview","report","map","queue","detail","analytics","audit","users"},
        "officer": {"overview","report","map","queue","detail","analytics"},
        "citizen": {"overview","report","map","my","detail"},
        "guest":   {"overview","map"},
    }.get(role, {"overview", "map"})

    return [(k, label, mod) for k, label, mod in all_pages if k in visible]


def render_sidebar(user: dict) -> str:
    """Render sidebar nav; return the selected page key."""
    logo_path = Path("assets/icon.png")

    with st.sidebar:
        # Logo + wordmark
        col_logo, col_text = st.columns([1, 3])
        with col_logo:
            if logo_path.exists():
                st.image(str(logo_path), width=40)
        with col_text:
            st.markdown(
                '<div style="padding-top:4px">'
                '<span style="font-size:18px;font-weight:800;color:#FFFFFF">Urban</span>'
                '<span style="font-size:18px;font-weight:800;color:#1B9C85">Lens</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        st.markdown('<div style="margin-bottom:0.5rem"></div>', unsafe_allow_html=True)

        pages = _role_nav(user.get("role", "guest"))

        # Initialize session nav
        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = pages[0][0] if pages else "overview"

        # Check if coming from issue detail link
        if "goto_page" in st.session_state:
            st.session_state["nav_page"] = st.session_state.pop("goto_page")

        for key, label, _ in pages:
            is_active = st.session_state.get("nav_page") == key
            active_style = "background:rgba(27,156,133,0.18);" if is_active else ""
            if st.button(
                label,
                key=f"nav_{key}",
                use_container_width=True,
            ):
                st.session_state["nav_page"] = key
                st.rerun()

        # User block
        sidebar_user_block(user)

        if user.get("role") != "guest":
            st.markdown('<div style="margin-top:0.5rem"></div>', unsafe_allow_html=True)
            if st.button("Sign out", key="signout_btn", use_container_width=True):
                logout()
                st.rerun()

    return st.session_state.get("nav_page", pages[0][0] if pages else "overview")


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

if not is_authenticated():
    login_page.render()
else:
    user = current_user()
    page_key = render_sidebar(user)

    # Route to selected page
    page_map = {k: mod for k, _, mod in _role_nav(user.get("role", "guest"))}
    page_mod = page_map.get(page_key)
    if page_mod:
        page_mod.render()
    else:
        st.error("Page not found.")
