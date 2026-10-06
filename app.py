"""
UrbanLens — AI Municipal Infrastructure Operations Platform.
Main application router and role-based navigation orchestrator.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

# ── 1. Page Configuration (Must be first Streamlit call) ──────────────────────
st.set_page_config(
    page_title="UrbanLens · Infrastructure Operations",
    page_icon="assets/icon.png" if Path("assets/icon.png").exists() else "🏙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. Database Initialization & Auto-Seed ────────────────────────────────────
from core.db import init_db, db_is_empty

init_db()
if db_is_empty():
    from seed import seed
    with st.spinner("Initializing UrbanLens database with municipal seed data…"):
        seed()

# ── 3. Map Tile Health Check (Startup verification) ───────────────────────────
from core.mapkit import get_healthy_tiles
get_healthy_tiles()

# ── 4. Authentication & Global State ──────────────────────────────────────────
from core.auth import current_user, logout, is_authenticated, continue_as_guest
from ui.theme import inject_css, TOKENS
from ui.components import sidebar_user_card, friendly_error_card

# ── 5. View Module Imports ────────────────────────────────────────────────────
import views.landing as landing_view
import views.login as login_view
import views.overview as overview_view
import views.map as map_view
import views.report as report_view
import views.my_reports as my_reports_view
import views.queue as queue_view
import views.analytics as analytics_view
import views.assistant as assistant_view
import views.audit_log as audit_log_view
import views.users as users_view
import views.issue_detail as issue_detail_view


def _wrap_safe(render_fn, title: str):
    """Wrap view execution in a safety net that displays a friendly error card instead of a blank page."""
    def _safe_runner():
        try:
            render_fn()
        except PermissionError as pe:
            friendly_error_card(
                "Access Restricted",
                f"You do not have permission to view {title}. {pe}",
            )
        except Exception as exc:
            friendly_error_card(
                f"{title} Encountered an Error",
                "An unexpected issue occurred while rendering this view. Your data is safe.",
                exc=exc,
            )
    return _safe_runner


# ── 6. Top Sidebar Branding & User Controls ───────────────────────────────────
def _render_sidebar_header():
    """Render crisp logo icon and white wordmark at the top of the navy sidebar."""
    icon_path = Path("assets/icon.png")
    st.sidebar.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;padding:0.75rem 0.25rem 1.25rem 0.25rem;border-bottom:1px solid rgba(255,255,255,0.12);margin-bottom:0.75rem">
          <img src="data:image/png;base64,{_get_icon_b64()}" style="width:40px;height:40px;border-radius:8px;object-fit:contain"/>
          <div>
            <div style="font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#FFFFFF;line-height:1.1">
              Urban<span style="color:#1B9C85">Lens</span>
            </div>
            <div style="font-size:11px;color:#9AC4E8;letter-spacing:0.04em;text-transform:uppercase;font-weight:600">
              Civic Operations
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _get_icon_b64() -> str:
    import base64
    p = Path("assets/icon.png")
    if p.exists():
        try:
            return base64.b64encode(p.read_bytes()).decode("utf-8")
        except Exception:
            return ""
    return ""


def _render_sidebar_footer(user: dict):
    """Render user card and sign out button at the bottom of the sidebar."""
    sidebar_user_card(user)
    st.sidebar.markdown('<div style="margin-top:0.5rem"></div>', unsafe_allow_html=True)
    if user.get("role") != "guest":
        if st.sidebar.button("Sign Out", key="sidebar_signout_btn", use_container_width=True):
            logout()
            st.session_state["auth_view"] = "landing"
            st.rerun()
    else:
        if st.sidebar.button("Sign In to Full Portal", key="sidebar_signin_guest_btn", use_container_width=True, type="primary"):
            logout()
            st.session_state["auth_view"] = "login"
            st.rerun()


# ── 7. Main Router Logic ──────────────────────────────────────────────────────
if not is_authenticated():
    # Hide sidebar for landing and login views
    inject_css(hide_sidebar=True)

    auth_view = st.session_state.get("auth_view", "landing")
    if auth_view == "login":
        login_view.render(on_back_to_landing=lambda: st.session_state.update({"auth_view": "landing"}))
    else:
        landing_view.render(on_sign_in_click=lambda: st.session_state.update({"auth_view": "login"}))

else:
    # User is authenticated (or exploring in guest mode)
    user = current_user()
    role = user.get("role", "guest")
    inject_css(hide_sidebar=False)

    _render_sidebar_header()

    # Build Navigation Pages per Role
    if role == "guest":
        pages = [
            st.Page(_wrap_safe(map_view.render, "Public Map"), title="Public Map", icon=":material/map:", default=True),
            st.Page(_wrap_safe(login_view.render, "Sign In"), title="Sign In", icon=":material/login:"),
        ]
    elif role == "citizen":
        pages = [
            st.Page(_wrap_safe(overview_view.render, "Dashboard"), title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page(_wrap_safe(report_view.render, "Report Issue"), title="Report Issue", icon=":material/add_a_photo:"),
            st.Page(_wrap_safe(my_reports_view.render, "My Reports"), title="My Reports", icon=":material/folder_open:"),
            st.Page(_wrap_safe(map_view.render, "Live Map"), title="Live Map", icon=":material/map:"),
        ]
    elif role == "officer":
        pages = [
            st.Page(_wrap_safe(overview_view.render, "Dashboard"), title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page(_wrap_safe(map_view.render, "Live Map"), title="Live Map", icon=":material/map:"),
            st.Page(_wrap_safe(queue_view.render, "Repair Queue"), title="Repair Queue", icon=":material/format_list_numbered:"),
            st.Page(_wrap_safe(analytics_view.render, "Analytics"), title="Analytics", icon=":material/analytics:"),
            st.Page(_wrap_safe(assistant_view.render, "Ask UrbanLens"), title="Ask UrbanLens", icon=":material/search:"),
            st.Page(_wrap_safe(report_view.render, "Report Issue"), title="Report Issue", icon=":material/add_a_photo:"),
        ]
    else:  # Admin
        pages = {
            "Operations": [
                st.Page(_wrap_safe(overview_view.render, "Dashboard"), title="Dashboard", icon=":material/dashboard:", default=True),
                st.Page(_wrap_safe(map_view.render, "Live Map"), title="Live Map", icon=":material/map:"),
                st.Page(_wrap_safe(queue_view.render, "Repair Queue"), title="Repair Queue", icon=":material/format_list_numbered:"),
                st.Page(_wrap_safe(analytics_view.render, "Analytics"), title="Analytics", icon=":material/analytics:"),
                st.Page(_wrap_safe(assistant_view.render, "Ask UrbanLens"), title="Ask UrbanLens", icon=":material/search:"),
                st.Page(_wrap_safe(report_view.render, "Report Issue"), title="Report Issue", icon=":material/add_a_photo:"),
            ],
            "Administration": [
                st.Page(_wrap_safe(audit_log_view.render, "Audit Log"), title="Audit Log", icon=":material/history:"),
                st.Page(_wrap_safe(users_view.render, "Users & Roles"), title="Users & Roles", icon=":material/people:"),
            ],
        }

    # Execute Navigation
    pg = st.navigation(pages, position="sidebar")

    # Render User Card in Sidebar
    _render_sidebar_footer(user)

    # Run Active Page
    pg.run()
