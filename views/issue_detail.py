"""
Issue Detail View & Modal Dialog — Annotated image, metadata, AI inspection assessment,
score breakdown, status timeline, and immutable comments.
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go

from core.auth import current_user, has_permission
from core.config import ISSUE_LABELS
from core.db import (
    get_issue, get_comments, add_comment, update_issue_status,
    get_issue_images, get_conn
)
from core.audit import log_audit, issue_timeline
from core.ai_assess import generate_bilingual_summary, assess_image
from ui.components import (
    page_header, severity_badge, status_badge,
    relative_time, status_timeline, empty_state, ai_assessment_card, friendly_error_card
)
from ui.theme import TOKENS


def _meta_row(label: str, value: str) -> str:
    return (
        f'<div><div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
        f'text-transform:uppercase;margin-bottom:2px">{label}</div>'
        f'<div style="font-size:14px;color:{TOKENS["navy"]}">{value}</div></div>'
    )


def _render_score_breakdown(issue: dict) -> None:
    """Plotly bar chart showing how the severity score was composed."""
    sev_score = issue.get("severity_score", 0.0)
    loc_type  = issue.get("location_type", "default")
    report_count = issue.get("report_count", 1)

    from core.config import (
        WEIGHT_AREA_RATIO, WEIGHT_CONFIDENCE, WEIGHT_DETECT_COUNT, LOCATION_MULTIPLIERS
    )
    multiplier = LOCATION_MULTIPLIERS.get(loc_type, 1.0)

    components = [
        ("Area Coverage",     WEIGHT_AREA_RATIO,   "#136F63"),
        ("Confidence",        WEIGHT_CONFIDENCE,   "#1B9C85"),
        ("Detection Count",   WEIGHT_DETECT_COUNT, "#6CC48A"),
    ]

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
            f'<div style="font-size:20px;font-weight:700;color:{TOKENS["navy"]}">{sev_score:.3f}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div style="font-size:12px;color:{TOKENS["muted"]}">Location Multiplier</div>'
            f'<div style="font-size:20px;font-weight:700;color:{TOKENS["navy"]}">×{multiplier}</div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div style="font-size:12px;color:{TOKENS["muted"]}">Calculated Priority</div>'
            f'<div style="font-size:20px;font-weight:700;color:{TOKENS["teal_deep"]}">{issue.get("priority",0):.3f}</div>',
            unsafe_allow_html=True,
        )


def render_issue_body(issue_id: int, user: dict | None = None) -> None:
    """Render the full issue detail body."""
    if user is None:
        user = current_user()
    role = user.get("role", "guest")

    issue = get_issue(issue_id, user)
    if not issue:
        friendly_error_card(
            "Issue Not Found",
            f"Issue #{issue_id} could not be retrieved or you lack permission to view it.",
        )
        return

    type_label = ISSUE_LABELS.get(issue["type"], issue["type"])
    st.markdown(
        f"""
        <div style="border-bottom:1px solid {TOKENS['border']};padding-bottom:0.75rem;margin-bottom:1rem">
          <div style="font-size:22px;font-weight:700;color:{TOKENS['navy']}">
            Issue #{issue_id} — {type_label}
          </div>
          <div style="font-size:13px;color:{TOKENS['muted']}">
            {issue.get("area", "Unknown Area")} · Reported {relative_time(issue.get("created_at", ""))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Main Layout: Visual on Left, Metadata & Status on Right ───────────────
    col_img, col_meta = st.columns([3, 2], gap="medium")

    with col_img:
        img_path = issue.get("image_path", "")
        if img_path and Path(img_path).exists():
            st.image(img_path, use_container_width=True, caption="Verified hazard image")
        else:
            st.markdown(
                f'<div style="background:{TOKENS["bg"]};border:1px solid {TOKENS["border"]};'
                f'border-radius:8px;height:240px;display:flex;align-items:center;'
                f'justify-content:center;color:{TOKENS["muted"]};font-size:13px">'
                f'No image visual available</div>',
                unsafe_allow_html=True,
            )

        # Additional images if any
        extra_imgs = get_issue_images(issue_id)
        if extra_imgs:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{TOKENS["muted"]};margin:0.75rem 0 0.3rem">Additional photos ({len(extra_imgs)})</div>', unsafe_allow_html=True)
            img_cols = st.columns(min(len(extra_imgs), 4))
            for i, ei in enumerate(extra_imgs[:4]):
                if Path(ei["image_path"]).exists():
                    with img_cols[i]:
                        st.image(ei["image_path"], use_container_width=True)

    with col_meta:
        st.markdown(
            f"""
            <div style="background:#FFFFFF;border:1px solid {TOKENS['border']};border-radius:10px;padding:1.25rem">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.85rem">
                {_meta_row("Type", type_label)}
                {_meta_row("Severity", severity_badge(issue["severity_label"]))}
                {_meta_row("Status", status_badge(issue["status"]))}
                {_meta_row("Priority", f'<strong class="tabnum">{issue["priority"]:.3f}</strong>')}
                {_meta_row("Area", issue.get("area", "—"))}
                {_meta_row("Reports Merged", str(issue.get("report_count", 1)))}
                {_meta_row("Reported By", issue.get("reported_by") or "Anonymous")}
                {_meta_row("Assigned To", issue.get("assigned_to") or "Unassigned")}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if issue.get("lat") and issue.get("lon"):
            st.markdown(
                f'<div style="font-size:12px;color:{TOKENS["muted"]};margin-top:0.5rem">'
                f'Coordinates: {issue["lat"]:.5f}, {issue["lon"]:.5f}</div>',
                unsafe_allow_html=True,
            )

        # Status Transition Control (Officers / Admins)
        if has_permission(user, "assign_status"):
            st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)
            statuses = ["reported", "assigned", "fixed"]
            curr_idx = statuses.index(issue["status"]) if issue["status"] in statuses else 0
            new_st = st.selectbox(
                "Update Resolution Status",
                statuses,
                index=curr_idx,
                key=f"dialog_status_sel_{issue_id}",
                format_func=lambda s: s.capitalize(),
            )
            if st.button("Save Status Change", key=f"dialog_status_btn_{issue_id}", type="primary", use_container_width=True):
                try:
                    update_issue_status(user, issue_id, new_st)
                    log_audit(user["username"], role, new_st, issue_id, f"Status updated to {new_st}")
                    st.success("Status updated successfully.")
                    st.rerun()
                except PermissionError as e:
                    st.error(str(e))

    # ── AI Inspection Assessment (Google Gemini) ──────────────────────────────
    assess_data = None
    if issue.get("ai_assessment"):
        try:
            assess_data = json.loads(issue["ai_assessment"])
        except Exception:
            assess_data = None

    if assess_data:
        st.markdown('<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)
        model_tag = issue.get("ai_model") or "Google Gemini"
        ai_assessment_card(assess_data, model_name=model_tag)

        # Bilingual Summary
        c_lang, c_sum = st.columns([1, 4])
        with c_lang:
            lang_choice = st.radio(
                "Language",
                options=["English", "हिंदी (Hindi)"],
                key=f"dialog_lang_{issue_id}",
            )
        with c_sum:
            lang_code = "hi" if "Hindi" in lang_choice else "en"
            summary_text = generate_bilingual_summary(assess_data, language=lang_code, actor=user)
            if summary_text:
                st.markdown(
                    f"""
                    <div style="background:#F0F7F6;border-left:3px solid {TOKENS['teal_deep']};padding:0.75rem 1rem;border-radius:4px;font-size:13px;color:{TOKENS['navy']};line-height:1.5">
                      <strong>Executive Summary ({lang_choice.split()[0]}):</strong> {summary_text}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    elif has_permission(user, "assign_status"):
        if st.button("Run Gemini Inspection Assessment", key=f"run_gemini_diag_{issue_id}"):
            with st.spinner("Analyzing image with Google Gemini…"):
                img_path = issue.get("image_path", "")
                if img_path and Path(img_path).exists():
                    from PIL import Image as PILImage
                    pil_img = PILImage.open(img_path)
                    res_assess = assess_image(pil_img, actor=user)
                    if res_assess:
                        res_dict = res_assess.model_dump()
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE issues SET ai_assessment=?, ai_model=? WHERE id=?",
                                (json.dumps(res_dict), "Google Gemini", issue_id),
                            )
                        st.success("AI qualitative assessment completed.")
                        st.rerun()
                    else:
                        st.warning("AI assessment unavailable (offline or inactive key).")

    # ── Tabs: Score Breakdown | Status Stepper | Audit & Comments ─────────────
    st.markdown('<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)
    tab_score, tab_timeline, tab_comments = st.tabs(["Priority Breakdown", "Status Stepper", "Comments & Audit"])

    with tab_score:
        _render_score_breakdown(issue)

    with tab_timeline:
        audit_rows = issue_timeline(issue_id)
        if audit_rows:
            status_timeline(audit_rows)
        else:
            empty_state("No timeline history", "Timeline events will appear here as field crews take action.")

    with tab_comments:
        comments = get_comments(issue_id)
        if comments:
            for c in comments:
                role_color = {"admin": TOKENS["high"], "officer": TOKENS["teal_deep"]}.get(c["role"], TOKENS["muted"])
                st.markdown(
                    f"""
                    <div style="padding:0.75rem 0;border-bottom:1px solid {TOKENS['border']}">
                      <div style="font-size:12px;margin-bottom:4px">
                        <strong style="color:{TOKENS['navy']}">{c['user']}</strong>
                        <span style="background:{role_color}22;color:{role_color};border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700;text-transform:uppercase">{c['role']}</span>
                        <span style="color:{TOKENS['muted']}">{relative_time(c['created_at'])}</span>
                      </div>
                      <div style="font-size:13px;color:{TOKENS['navy']}">{c['text']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(f'<div style="color:{TOKENS["muted"]};font-size:13px;padding:0.75rem 0">No internal comments logged.</div>', unsafe_allow_html=True)

        if has_permission(user, "add_comment"):
            comment_text = st.text_area("Add internal comment", key=f"comm_input_{issue_id}", height=75)
            if st.button("Post Comment", key=f"comm_post_{issue_id}"):
                if comment_text.strip():
                    try:
                        add_comment(user, issue_id, comment_text.strip())
                        log_audit(user["username"], role, "comment", issue_id, "Added comment")
                        st.success("Comment posted.")
                        st.rerun()
                    except PermissionError as e:
                        st.error(str(e))


@st.dialog("Issue Details", width="large")
def open_issue_dialog(issue_id: int):
    """Modal dialog for inspecting an issue without leaving the current view."""
    render_issue_body(issue_id)


def render() -> None:
    """Direct page renderer (if navigated to directly)."""
    issue_id = st.session_state.get("detail_issue_id")
    if not issue_id:
        st.info("Select an issue from the Dashboard, Live Map, or Repair Queue to view full details.")
        inp = st.number_input("Or enter Issue ID directly:", min_value=1, step=1, key="direct_issue_id_inp")
        if st.button("Open Issue", key="direct_issue_open_btn", type="primary"):
            st.session_state["detail_issue_id"] = int(inp)
            st.rerun()
        return

    render_issue_body(issue_id)
