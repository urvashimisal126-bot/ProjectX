"""Issue Detail page — annotated image, metadata, score breakdown, timeline, comments."""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import plotly.graph_objects as go

from core.auth import current_user, require_role
from core.config import ISSUE_LABELS
from core.db import get_issue, get_comments, add_comment, update_issue_status, get_issue_images, has_permission
from core.audit import log_audit, issue_timeline
from core.score import severity_breakdown
from ui.components import (
    page_header, severity_badge, status_badge,
    relative_time, status_timeline, empty_state,
)
from ui.theme import TOKENS


def render() -> None:
    user = current_user()
    role = user.get("role", "guest")

    # Get issue ID from session state (set by map/queue click)
    issue_id = st.session_state.get("detail_issue_id")

    if not issue_id:
        st.markdown(
            f'<div style="padding:2rem;text-align:center;color:{TOKENS["muted"]}">'
            f'Select an issue from the Repair Queue or Live Map to view its detail.</div>',
            unsafe_allow_html=True,
        )
        # Allow direct entry
        inp = st.number_input("Or enter issue ID directly:", min_value=1, step=1, key="manual_issue_id")
        if st.button("Load Issue", key="load_issue_btn"):
            st.session_state["detail_issue_id"] = int(inp)
            st.rerun()
        return

    issue = get_issue(issue_id, user)
    if not issue:
        st.error(f"Issue #{issue_id} not found or you do not have permission to view it.")
        st.session_state.pop("detail_issue_id", None)
        return

    page_header(
        f'Issue #{issue_id} — {ISSUE_LABELS.get(issue["type"], issue["type"])}',
        f'{issue.get("area", "Unknown area")} · Reported {relative_time(issue["created_at"])}',
    )

    # ── Main columns ──────────────────────────────────────────────────────────
    col_img, col_meta = st.columns([3, 2])

    with col_img:
        img_path = issue.get("image_path", "")
        if img_path and Path(img_path).exists():
            st.image(img_path, use_container_width=True, caption="Annotated detection image")
        else:
            st.markdown(
                f'<div style="background:{TOKENS["bg"]};border:1px solid {TOKENS["border"]};'
                f'border-radius:8px;height:280px;display:flex;align-items:center;'
                f'justify-content:center;color:{TOKENS["muted"]};font-size:13px">'
                f'No image available</div>',
                unsafe_allow_html=True,
            )

        # Additional images
        extra_imgs = get_issue_images(issue_id)
        if extra_imgs:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{TOKENS["muted"]};margin:0.75rem 0 0.3rem">Additional photos ({len(extra_imgs)})</div>', unsafe_allow_html=True)
            img_cols = st.columns(min(len(extra_imgs), 4))
            for i, ei in enumerate(extra_imgs[:4]):
                if Path(ei["image_path"]).exists():
                    with img_cols[i]:
                        st.image(ei["image_path"], use_container_width=True)

    with col_meta:
        # Metadata card
        st.markdown(
            f'<div style="background:#fff;border:1px solid {TOKENS["border"]};'
            f'border-radius:10px;padding:1.25rem">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">'
            + _meta_row("Type",     ISSUE_LABELS.get(issue["type"], issue["type"]))
            + _meta_row("Severity", severity_badge(issue["severity_label"]))
            + _meta_row("Status",   status_badge(issue["status"]))
            + _meta_row("Priority", f'<strong class="tabnum">{issue["priority"]:.3f}</strong>')
            + _meta_row("Area",     issue.get("area", "—"))
            + _meta_row("Reports",  str(issue.get("report_count", 1)))
            + _meta_row("Reported by", issue.get("reported_by", "—"))
            + _meta_row("Assigned to", issue.get("assigned_to") or "—")
            + f'</div></div>',
            unsafe_allow_html=True,
        )

        if issue.get("lat") and issue.get("lon"):
            st.markdown(
                f'<div style="font-size:12px;color:{TOKENS["muted"]};margin-top:0.5rem">'
                f'GPS: {issue["lat"]:.5f}, {issue["lon"]:.5f}</div>',
                unsafe_allow_html=True,
            )

        # Status change (officer/admin)
        if has_permission(user, "assign_status"):
            st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)
            statuses = ["reported", "assigned", "fixed"]
            new_st = st.selectbox(
                "Update status",
                statuses,
                index=statuses.index(issue["status"]),
                key="detail_status_sel",
            )
            if st.button("Update Status", key="detail_update_btn"):
                try:
                    update_issue_status(user, issue_id, new_st)
                    log_audit(user["username"], role, new_st, issue_id, f"Status → {new_st}")
                    st.success("Status updated.")
                    st.rerun()
                except PermissionError as e:
                    st.error(str(e))

    # ── Tabs: Score Breakdown | Timeline | Comments ───────────────────────────
    tab_score, tab_timeline, tab_comments = st.tabs(["Score Breakdown", "Status Timeline", "Comments"])

    with tab_score:
        _render_score_breakdown(issue)

    with tab_timeline:
        audit_rows = issue_timeline(issue_id)
        if audit_rows:
            status_timeline(audit_rows)
        else:
            empty_state("No timeline yet", "Events will appear here as the issue progresses.")

    with tab_comments:
        comments = get_comments(issue_id)
        if comments:
            for c in comments:
                role_color = {"admin": TOKENS["high"], "officer": TOKENS["teal_deep"]}.get(c["role"], TOKENS["muted"])
                st.markdown(
                    f'<div style="padding:0.75rem 0;border-bottom:1px solid {TOKENS["border"]}">'
                    f'<div style="font-size:12px;margin-bottom:4px">'
                    f'<strong style="color:{TOKENS["navy"]}">{c["user"]}</strong> '
                    f'<span style="background:{role_color}22;color:{role_color};border-radius:3px;'
                    f'padding:1px 6px;font-size:10px;font-weight:700;text-transform:uppercase">{c["role"]}</span> '
                    f'<span style="color:{TOKENS["muted"]}">{relative_time(c["created_at"])}</span>'
                    f'</div>'
                    f'<div style="font-size:13px;color:{TOKENS["navy"]}">{c["text"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(f'<div style="color:{TOKENS["muted"]};font-size:13px;padding:1rem 0">No comments yet.</div>', unsafe_allow_html=True)

        if has_permission(user, "add_comment"):
            comment_text = st.text_area("Add a comment", key="new_comment", height=80)
            if st.button("Post Comment", key="post_comment_btn"):
                if comment_text.strip():
                    try:
                        add_comment(user, issue_id, comment_text.strip())
                        log_audit(user["username"], role, "comment", issue_id, "Added comment")
                        st.success("Comment posted.")
                        st.rerun()
                    except PermissionError as e:
                        st.error(str(e))
                else:
                    st.warning("Please enter a comment before posting.")


def _meta_row(label: str, value: str) -> str:
    return (
        f'<div><div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
        f'text-transform:uppercase;margin-bottom:2px">{label}</div>'
        f'<div style="font-size:13px;color:{TOKENS["navy"]}">{value}</div></div>'
    )


def _render_score_breakdown(issue: dict) -> None:
    """Plotly bar chart showing how the severity score was composed."""
    # Reconstruct breakdown using stored data
    sev_score = issue.get("severity_score", 0)
    loc_type  = issue.get("location_type", "default")
    report_count = issue.get("report_count", 1)

    # Estimate components (we store final score; show best-effort breakdown)
    from core.config import (  # noqa: PLC0415
        WEIGHT_AREA_RATIO, WEIGHT_CONFIDENCE, WEIGHT_DETECT_COUNT, LOCATION_MULTIPLIERS
    )
    multiplier = LOCATION_MULTIPLIERS.get(loc_type, 1.0)

    components = [
        ("Area Coverage",     WEIGHT_AREA_RATIO,   "#136F63"),
        ("Confidence",        WEIGHT_CONFIDENCE,   "#1B9C85"),
        ("Detection Count",   WEIGHT_DETECT_COUNT, "#6CC48A"),
    ]

    # Distribute proportionally
    total_weight = sum(w for _, w, _ in components)
    labels = [c[0] for c in components]
    values = [round(sev_score * c[1] / total_weight, 3) for c in components]
    colors = [c[2] for c in components]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.3f}" for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=180,
        margin=dict(l=0, r=40, t=10, b=10),
        xaxis=dict(range=[0, 0.6], showgrid=True, gridcolor="#E3E8EF", zeroline=False),
        yaxis=dict(showgrid=False),
        font=dict(family="Inter", size=12, color="#0B2545"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div style="font-size:12px;color:{TOKENS["muted"]}">Severity Score</div>'
            f'<div style="font-size:22px;font-weight:700;color:{TOKENS["navy"]}">{sev_score:.3f}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div style="font-size:12px;color:{TOKENS["muted"]}">Location Multiplier</div>'
            f'<div style="font-size:22px;font-weight:700;color:{TOKENS["navy"]}">×{multiplier}</div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div style="font-size:12px;color:{TOKENS["muted"]}">Priority Score</div>'
            f'<div style="font-size:22px;font-weight:700;color:{TOKENS["teal_deep"]}">{issue.get("priority",0):.3f}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="font-size:12px;color:{TOKENS["muted"]};margin-top:0.5rem">'
        f'Formula: severity × location_multiplier × (1 + 0.1 × (report_count − 1))<br>'
        f'Location type: <strong>{loc_type}</strong> · Reports: <strong>{report_count}</strong></div>',
        unsafe_allow_html=True,
    )
