"""
Repair Queue page — Municipal dispatch and triage queue for field crews and administrators.
Ranked work orders, filtering, inline status progression, and CSV export.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import current_user, require_role
from core.config import ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
from core.db import list_issues, update_issue_status, list_users, has_permission
from core.audit import log_audit
from ui.components import page_header, severity_badge, status_badge, relative_time, empty_state
from ui.theme import TOKENS
from views.issue_detail import open_issue_dialog


def render() -> None:
    require_role(["admin", "officer"])
    user = current_user()

    page_header("Repair Queue", "Prioritized municipal work orders — triage, update statuses, and dispatch crews.", live=True)

    # ── Filters ────────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.8, 1.3, 1.3, 1.3, 1.3, 1.3])
    with fc1:
        search = st.text_input("Search Area", placeholder="e.g. Vijay Nagar", key="q_search")
    with fc2:
        f_type = st.multiselect("Hazard Type", ISSUE_CLASSES, format_func=lambda x: ISSUE_LABELS.get(x, x), key="q_type")
    with fc3:
        f_sev = st.multiselect("Severity", ["High", "Medium", "Low"], key="q_sev")
    with fc4:
        f_status = st.multiselect("Status", ["reported", "assigned", "fixed"], key="q_status")
    with fc5:
        f_verify = st.selectbox("Verification", ["All", "Unverified", "Verified", "Rejected"], key="q_verify")
    with fc6:
        if has_permission(user, "manage_users"):
            try:
                officers = [u for u in list_users(user) if u["role"] in ("officer", "admin")]
                officer_names = ["All"] + [u["username"] for u in officers]
            except Exception:
                officer_names = ["All"]
        else:
            officer_names = ["All"]
        f_officer = st.selectbox("Assignee", officer_names, key="q_officer")

    filters = {}
    if f_type:
        filters["type"] = f_type
    if f_sev:
        filters["severity_label"] = f_sev
    if f_status:
        filters["status"] = f_status
    if search:
        filters["area"] = search
    if f_officer and f_officer != "All":
        filters["assigned_to"] = f_officer

    issues = list_issues(user, filters)
    if f_verify and f_verify != "All":
        target_v = f_verify.lower()
        issues = [i for i in issues if i.get("verification_status", "unverified") == target_v]

    # ── Export & Count Bar ─────────────────────────────────────────────────────
    col_count, col_export = st.columns([3, 1])
    with col_count:
        st.markdown(
            f'<div style="font-size:14px;color:{TOKENS["muted"]};margin:0.5rem 0">'
            f'Found <strong>{len(issues)}</strong> work orders matching active filters</div>',
            unsafe_allow_html=True,
        )
    with col_export:
        if has_permission(user, "export_csv") and issues:
            df_export = pd.DataFrame(issues)
            csv = df_export.to_csv(index=False)
            st.download_button(
                "Export Work Orders (.CSV)",
                data=csv,
                file_name="urbanlens_repair_queue.csv",
                mime="text/csv",
                key="q_export",
                use_container_width=True,
            )
            log_audit(user["username"], user["role"], "export", None, f"Exported {len(issues)} issues from queue")

    if not issues:
        empty_state("No work orders found", "Adjust search filters to view other assigned or closed work orders.")
        return

    # ── Ranked Queue Table ────────────────────────────────────────────────────
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([0.6, 0.9, 2.2, 1.1, 1.1, 1.3, 1.2, 2.0])
    for col, label in zip(
        [h1, h2, h3, h4, h5, h6, h7, h8],
        ["#", "Priority", "Hazard & Location", "Severity", "Status", "Verification", "Reported", "Actions & Triage"],
    ):
        with col:
            st.markdown(
                f'<div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
                f'text-transform:uppercase;padding:6px 0;border-bottom:2px solid {TOKENS["border"]}">'
                f'{label}</div>',
                unsafe_allow_html=True,
            )

    for iss in issues:
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.6, 0.9, 2.2, 1.1, 1.1, 1.3, 1.2, 2.0])
        with c1:
            st.markdown(f'<span style="font-size:13px;font-weight:600;color:{TOKENS["muted"]}">#{iss["id"]}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<span style="font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;color:{TOKENS["navy"]}">{iss["priority"]:.3f}</span>', unsafe_allow_html=True)
        with c3:
            type_label = ISSUE_LABELS.get(iss["type"], iss["type"])
            st.markdown(
                f'<span style="font-size:14px;font-weight:600;color:{TOKENS["navy"]}">{type_label}</span>'
                f'<br><span style="font-size:12px;color:{TOKENS["muted"]}">{iss.get("area", "—")}</span>',
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(severity_badge(iss["severity_label"]), unsafe_allow_html=True)
        with c5:
            st.markdown(status_badge(iss["status"]), unsafe_allow_html=True)
        with c6:
            v_stat = iss.get("verification_status", "unverified")
            if v_stat == "verified":
                st.markdown('<span style="background:rgba(27,156,133,0.12);color:#136F63;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">Verified</span>', unsafe_allow_html=True)
            elif v_stat == "rejected":
                st.markdown('<span style="background:rgba(239,68,68,0.12);color:#C8372D;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">Rejected</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="background:rgba(100,116,139,0.12);color:#64748B;font-size:11px;font-weight:700;padding:2px 6px;border-radius:4px;">Pending</span>', unsafe_allow_html=True)
        with c7:
            st.markdown(f'<span style="font-size:13px;color:{TOKENS["muted"]}">{relative_time(iss["created_at"])}</span>', unsafe_allow_html=True)
        with c8:
            a1, a2 = st.columns([1.5, 1.0])
            with a1:
                new_status = st.selectbox(
                    "Status",
                    ["reported", "assigned", "fixed"],
                    index=["reported", "assigned", "fixed"].index(iss["status"]),
                    key=f"status_sel_{iss['id']}",
                    label_visibility="collapsed",
                    format_func=lambda s: s.capitalize(),
                )
                if new_status != iss["status"]:
                    try:
                        update_issue_status(user, iss["id"], new_status)
                        log_audit(user["username"], user["role"], new_status, iss["id"], f"Status -> {new_status}")
                        st.rerun()
                    except PermissionError as e:
                        st.error(str(e))
            with a2:
                if st.button("Inspect", key=f"q_inspect_{iss['id']}", use_container_width=True):
                    open_issue_dialog(iss["id"])

        st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]};margin:4px 0"></div>', unsafe_allow_html=True)
