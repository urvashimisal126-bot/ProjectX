"""Repair Queue page — Admin and Officer only."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core.auth import current_user, require_role
from core.config import ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
from core.db import list_issues, update_issue_status, list_users, has_permission
from core.audit import log_audit
from ui.components import page_header, severity_badge, status_badge, relative_time, empty_state
from ui.theme import TOKENS


def render() -> None:
    require_role(["admin", "officer"])
    user = current_user()

    page_header("Repair Queue", "Ranked list of all open issues — assign, update status, and export.", live=True)

    # ── Filters ────────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
    with fc1:
        search = st.text_input("Search area", placeholder="e.g. Vijay Nagar", key="q_search")
    with fc2:
        f_type = st.multiselect("Type", ISSUE_CLASSES, format_func=lambda x: ISSUE_LABELS.get(x, x), key="q_type")
    with fc3:
        f_sev = st.multiselect("Severity", ["High", "Medium", "Low"], key="q_sev")
    with fc4:
        f_status = st.multiselect("Status", ["reported", "assigned", "fixed"], key="q_status")
    with fc5:
        if has_permission(user, "manage_users"):
            try:
                officers = [u for u in list_users(user) if u["role"] in ("officer", "admin")]
                officer_names = [""] + [u["username"] for u in officers]
            except Exception:
                officer_names = [""]
        else:
            officer_names = [""]
        f_officer = st.selectbox("Assigned to", officer_names, key="q_officer")

    filters = {}
    if f_type:    filters["type"] = f_type
    if f_sev:     filters["severity_label"] = f_sev
    if f_status:  filters["status"] = f_status
    if search:    filters["area"] = search
    if f_officer: filters["assigned_to"] = f_officer

    issues = list_issues(user, filters)

    # ── Export ─────────────────────────────────────────────────────────────────
    col_count, col_export = st.columns([3, 1])
    with col_count:
        st.markdown(
            f'<div style="font-size:13px;color:{TOKENS["muted"]};margin:0.5rem 0">'
            f'<strong>{len(issues)}</strong> issues found</div>',
            unsafe_allow_html=True,
        )
    with col_export:
        if has_permission(user, "export_csv") and issues:
            df_export = pd.DataFrame(issues)
            csv = df_export.to_csv(index=False)
            st.download_button(
                "Export CSV",
                data=csv,
                file_name="urbanlens_queue.csv",
                mime="text/csv",
                key="q_export",
                use_container_width=True,
            )
            log_audit(user["username"], user["role"], "export", None, f"Exported {len(issues)} issues")

    if not issues:
        empty_state("No issues found", "Adjust filters or add a new report.")
        return

    # ── Table ──────────────────────────────────────────────────────────────────
    # Headers
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([0.4, 0.8, 1.4, 0.9, 0.9, 1.2, 1.2, 1.6])
    for col, label in zip(
        [h1, h2, h3, h4, h5, h6, h7, h8],
        ["#", "Priority", "Type / Area", "Severity", "Status", "Assigned", "Reported", "Actions"],
    ):
        with col:
            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
                f'text-transform:uppercase;padding:4px 0;border-bottom:2px solid {TOKENS["border"]}">'
                f'{label}</div>',
                unsafe_allow_html=True,
            )

    for iss in issues:
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.4, 0.8, 1.4, 0.9, 0.9, 1.2, 1.2, 1.6])
        with c1:
            st.markdown(f'<span style="font-size:12px;color:{TOKENS["muted"]}">#{iss["id"]}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<span style="font-size:13px;font-weight:700;font-variant-numeric:tabular-nums">{iss["priority"]:.3f}</span>', unsafe_allow_html=True)
        with c3:
            img_path = iss.get("image_path", "")
            from pathlib import Path  # noqa: PLC0415
            if img_path and Path(img_path).exists():
                st.image(img_path, width=48)
            st.markdown(
                f'<span style="font-size:13px;font-weight:600">{iss["type"].replace("_"," ").title()}</span>'
                f'<br><span style="font-size:11px;color:{TOKENS["muted"]}">{iss["area"]}</span>',
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(severity_badge(iss["severity_label"]), unsafe_allow_html=True)
        with c5:
            st.markdown(status_badge(iss["status"]), unsafe_allow_html=True)
        with c6:
            st.markdown(
                f'<span style="font-size:12px;color:{TOKENS["muted"]}">'
                f'{iss["assigned_to"] or "—"}</span>',
                unsafe_allow_html=True,
            )
        with c7:
            st.markdown(
                f'<span style="font-size:12px;color:{TOKENS["muted"]}">'
                f'{relative_time(iss["created_at"])}</span>',
                unsafe_allow_html=True,
            )
        with c8:
            a1, a2 = st.columns(2)
            with a1:
                new_status = st.selectbox(
                    "Status",
                    ["reported", "assigned", "fixed"],
                    index=["reported", "assigned", "fixed"].index(iss["status"]),
                    key=f"status_sel_{iss['id']}",
                    label_visibility="collapsed",
                )
            with a2:
                if st.button("Save", key=f"save_status_{iss['id']}"):
                    try:
                        update_issue_status(user, iss["id"], new_status)
                        log_audit(user["username"], user["role"], new_status, iss["id"],
                                  f"Status changed to {new_status}")
                        st.success(f"#{iss['id']} updated", icon="✓")
                        st.rerun()
                    except PermissionError as e:
                        st.error(str(e))

        st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]}"></div>', unsafe_allow_html=True)
