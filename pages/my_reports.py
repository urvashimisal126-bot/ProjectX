"""My Reports page — Citizen view of their own issues."""
from __future__ import annotations

import streamlit as st

from core.auth import current_user, require_role
from core.db import list_issues, get_issue_audit
from core.config import ISSUE_LABELS
from ui.components import (
    page_header, severity_badge, status_badge,
    relative_time, status_timeline, empty_state,
)
from ui.theme import TOKENS


def render() -> None:
    require_role(["citizen", "admin", "officer"])
    user = current_user()

    page_header("My Reports", "Issues you have reported and their current resolution status.")

    issues = list_issues(user)  # db.py enforces citizen sees only own

    if not issues:
        empty_state(
            "No reports yet",
            "Use 'Report Issue' to submit your first infrastructure report.",
        )
        return

    for iss in issues:
        with st.expander(
            f"#{iss['id']}  {ISSUE_LABELS.get(iss['type'], iss['type'])} — {iss['area']}  "
            f"({relative_time(iss['created_at'])})",
            expanded=False,
        ):
            col_img, col_detail = st.columns([1, 2])
            from pathlib import Path  # noqa: PLC0415
            with col_img:
                img = iss.get("image_path", "")
                if img and Path(img).exists():
                    st.image(img, use_container_width=True)
                else:
                    st.markdown(
                        f'<div style="background:{TOKENS["bg"]};height:120px;'
                        f'border:1px solid {TOKENS["border"]};border-radius:6px;'
                        f'display:flex;align-items:center;justify-content:center;'
                        f'color:{TOKENS["muted"]};font-size:12px">No image</div>',
                        unsafe_allow_html=True,
                    )
            with col_detail:
                st.markdown(
                    f'{severity_badge(iss["severity_label"])} &nbsp; {status_badge(iss["status"])}',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="margin-top:0.75rem;font-size:13px">'
                    f'<strong>Priority:</strong> <span class="tabnum">{iss["priority"]:.3f}</span><br>'
                    f'<strong>Assigned to:</strong> {iss.get("assigned_to") or "Pending"}<br>'
                    f'<strong>Reports merged:</strong> {iss.get("report_count", 1)}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Timeline
            st.markdown(f'<div style="font-size:13px;font-weight:700;color:{TOKENS["navy"]};margin:0.75rem 0 0.25rem">Status Timeline</div>', unsafe_allow_html=True)
            audit_rows = get_issue_audit(iss["id"])
            if audit_rows:
                status_timeline(audit_rows)
            else:
                st.markdown(
                    f'<div style="font-size:12px;color:{TOKENS["muted"]}">No timeline events yet.</div>',
                    unsafe_allow_html=True,
                )

            if st.button(f"View Full Detail →", key=f"my_detail_{iss['id']}"):
                st.session_state["detail_issue_id"] = iss["id"]
                st.session_state["goto_page"] = "detail"
                st.rerun()
