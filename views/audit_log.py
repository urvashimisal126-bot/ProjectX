"""Audit Log page — Admin only."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import current_user, require_role
from core.db import get_audit_log, has_permission
from core.audit import log_audit
from ui.components import page_header, relative_time, empty_state
from ui.theme import TOKENS


def render() -> None:
    require_role(["admin"])
    user = current_user()

    page_header("Audit Log", "Complete, searchable record of all system actions.")

    # ── Filters ────────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        f_user = st.text_input("Filter by user", placeholder="e.g. admin", key="al_user")
    with fc2:
        f_action = st.selectbox(
            "Action",
            ["", "login", "login_failed", "logout", "upload", "merged", "assigned",
             "fixed", "reported", "denied", "export", "comment", "role_change", "deactivate"],
            key="al_action",
        )
    with fc3:
        limit = st.number_input("Limit", min_value=50, max_value=2000, value=200, step=50, key="al_limit")

    filters = {}
    if f_user:   filters["user"] = f_user
    if f_action: filters["action"] = f_action

    try:
        rows = get_audit_log(user, filters, limit=int(limit))
    except PermissionError as e:
        st.error(str(e))
        return

    # ── Export ─────────────────────────────────────────────────────────────────
    col_count, col_export = st.columns([3, 1])
    with col_count:
        st.markdown(
            f'<div style="font-size:13px;color:{TOKENS["muted"]};margin:0.5rem 0">'
            f'<strong>{len(rows)}</strong> log entries</div>',
            unsafe_allow_html=True,
        )
    with col_export:
        if rows:
            df_exp = pd.DataFrame(rows)
            csv = df_exp.to_csv(index=False)
            st.download_button(
                "Export CSV",
                data=csv,
                file_name="urbanlens_audit.csv",
                mime="text/csv",
                key="al_export",
                use_container_width=True,
            )
            log_audit(user["username"], user["role"], "export", None, f"Exported audit log ({len(rows)} rows)")

    if not rows:
        empty_state("No audit entries", "No log entries match the current filters.")
        return

    # ── Table ──────────────────────────────────────────────────────────────────
    ACTION_COLORS = {
        "denied":       TOKENS["high"],
        "login_failed": TOKENS["high"],
        "upload":       TOKENS["teal_deep"],
        "merged":       TOKENS["medium"],
        "fixed":        TOKENS["low"],
        "assigned":     TOKENS["assigned"],
    }

    # Headers
    h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1, 1.5, 0.8, 3, 1.5])
    for col, label in zip([h1, h2, h3, h4, h5, h6], ["User", "Role", "Action", "Issue", "Detail", "Time"]):
        with col:
            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
                f'text-transform:uppercase;padding:4px 0;border-bottom:2px solid {TOKENS["border"]}">'
                f'{label}</div>',
                unsafe_allow_html=True,
            )

    for row in rows:
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1, 1.5, 0.8, 3, 1.5])
        action_color = ACTION_COLORS.get(row["action"], TOKENS["navy"])
        with c1:
            st.markdown(f'<span style="font-size:12px;font-weight:600">{row["user"]}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<span style="font-size:11px;color:{TOKENS["muted"]}">{row["role"]}</span>', unsafe_allow_html=True)
        with c3:
            st.markdown(
                f'<span style="font-size:12px;font-weight:700;color:{action_color}">{row["action"]}</span>',
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f'<span style="font-size:12px;color:{TOKENS["muted"]}">'
                f'{"#" + str(row["issue_id"]) if row["issue_id"] else "—"}</span>',
                unsafe_allow_html=True,
            )
        with c5:
            st.markdown(f'<span style="font-size:12px;color:{TOKENS["muted"]}">{row["detail"] or "—"}</span>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<span style="font-size:11px;color:{TOKENS["muted"]}">{relative_time(row["timestamp"])}</span>', unsafe_allow_html=True)
        st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]}"></div>', unsafe_allow_html=True)
