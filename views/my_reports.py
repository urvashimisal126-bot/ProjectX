"""
My Reports page — Citizen view of their own reported infrastructure hazards.
Order-tracking style status timeline and verified visual evidence.
"""

from __future__ import annotations

from pathlib import Path
import streamlit as st

from core.auth import current_user, require_role
from core.db import list_issues, get_issue_audit
from core.config import ISSUE_LABELS
from ui.components import (
    page_header, severity_badge, status_badge,
    relative_time, status_timeline, empty_state
)
from ui.theme import TOKENS
from views.issue_detail import open_issue_dialog


def render() -> None:
    require_role(["citizen", "admin", "officer"])
    user = current_user()

    page_header(
        "My Reports",
        "Track the resolution progress of hazards you have reported to municipal maintenance.",
    )

    issues = list_issues(user)  # db.py enforces citizen sees only their own reports

    if not issues:
        empty_state(
            "No reports submitted yet",
            "Use the 'Report Issue' tab to submit your first infrastructure photo.",
        )
        return

    st.markdown(
        f'<div style="font-size:14px;color:{TOKENS["muted"]};margin-bottom:1rem">'
        f'You have submitted <strong>{len(issues)}</strong> reports</div>',
        unsafe_allow_html=True,
    )

    for iss in issues:
        type_lbl = ISSUE_LABELS.get(iss["type"], iss["type"])
        with st.expander(
            f"#{iss['id']} {type_lbl} — {iss.get('area','Unknown Area')} · Reported {relative_time(iss['created_at'])}",
            expanded=False,
        ):
            col_img, col_detail = st.columns([1, 2], gap="medium")
            with col_img:
                img = iss.get("image_path", "")
                if img and Path(img).exists():
                    st.image(img, use_container_width=True)
                else:
                    st.markdown(
                        f'<div style="background:{TOKENS["bg"]};height:120px;'
                        f'border:1px solid {TOKENS["border"]};border-radius:6px;'
                        f'display:flex;align-items:center;justify-content:center;'
                        f'color:{TOKENS["muted"]};font-size:12px">No visual image</div>',
                        unsafe_allow_html=True,
                    )
            with col_detail:
                st.markdown(
                    f'{severity_badge(iss["severity_label"])} &nbsp; {status_badge(iss["status"])}',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div style="margin-top:0.75rem;font-size:14px;color:{TOKENS['navy']};line-height:1.6">
                      <strong>Calculated Priority:</strong> <span class="tabnum">{iss['priority']:.3f}</span><br>
                      <strong>Field Assignee:</strong> {iss.get('assigned_to') or 'Pending municipal dispatch'}<br>
                      <strong>Citizen Confirmations:</strong> {iss.get('report_count', 1)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Timeline
            st.markdown(
                f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1rem 0 0.25rem">Resolution Progress Timeline</div>',
                unsafe_allow_html=True,
            )
            audit_rows = get_issue_audit(iss["id"])
            if audit_rows:
                status_timeline(audit_rows)
            else:
                st.markdown(
                    f'<div style="font-size:13px;color:{TOKENS["muted"]}">Report submitted and awaiting initial inspection.</div>',
                    unsafe_allow_html=True,
                )

            if st.button("Inspect Details & AI Assessment", key=f"my_detail_btn_{iss['id']}", type="primary"):
                open_issue_dialog(iss["id"])
