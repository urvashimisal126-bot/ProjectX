"""
Dashboard / Overview page — Role-personalized municipal command center.
Equal-height KPI cards (40px numerals), live map preview, top 5 priority list, and recent audit activity.
"""

from __future__ import annotations

import streamlit as st

from core.auth import current_user
from core.db import list_issues, kpi_counts, get_audit_log
from core.config import ISSUE_LABELS
from ui.components import page_header, kpi_card, severity_badge, status_badge, relative_time, empty_state
from ui.theme import TOKENS
from views.issue_detail import open_issue_dialog


def _mini_map_preview(issues: list[dict]) -> None:
    """Render a compact folium map preview."""
    try:
        from core.mapkit import build_map
        from streamlit_folium import st_folium
        m = build_map(issues[:40], compact=True)
        st_folium(m, height=320, width="100%", returned_objects=[], key="overview_mini_map")
    except Exception as e:
        st.info(f"Geospatial preview loading: {e}")


def render() -> None:
    user = current_user()
    role = user.get("role", "guest")

    page_header(
        "Dashboard",
        "Welcome to UrbanLens — Municipal infrastructure intelligence and triage command center.",
        live=True,
    )

    # ── 4 Equal-Height KPI Cards ──────────────────────────────────────────────
    kpis = kpi_counts(user)
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        kpi_card(
            label="Open Issues",
            value=str(kpis["total"]),
            hint="Active unresolved hazards",
        )
    with k2:
        high_cnt = kpis["high"]
        kpi_card(
            label="High Severity",
            value=str(high_cnt),
            delta="Critical triage priority" if high_cnt > 0 else "All high hazards clear",
            delta_good=high_cnt == 0,
        )
    with k3:
        hours = kpis["avg_fix_hours"]
        kpi_card(
            label="Avg. Time to Fix",
            value=f"{hours}h" if hours else "—",
            hint="Resolution turnaround time",
        )
    with k4:
        fixed_week = kpis["fixed_week"]
        kpi_card(
            label="Fixed This Week",
            value=str(fixed_week),
            delta=f"+{fixed_week} resolved" if fixed_week > 0 else "No repairs logged",
            delta_good=True,
        )

    st.markdown('<div style="margin-top:1.75rem"></div>', unsafe_allow_html=True)

    # ── Role-Specific Operational Content ─────────────────────────────────────
    issues = list_issues(user)
    open_issues = [i for i in issues if i["status"] != "fixed"]

    if role == "guest":
        col_map, col_sum = st.columns([3, 1], gap="medium")
        with col_map:
            st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Public Infrastructure Hazards</div>', unsafe_allow_html=True)
            _mini_map_preview(issues)
        with col_sum:
            st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Hazard Summary</div>', unsafe_allow_html=True)
            by_type = {}
            for iss in issues:
                lbl = ISSUE_LABELS.get(iss["type"], iss["type"])
                by_type[lbl] = by_type.get(lbl, 0) + 1
            for t, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:8px 0;'
                    f'border-bottom:1px solid {TOKENS["border"]};font-size:14px">'
                    f'<span>{t}</span><strong>{cnt}</strong></div>',
                    unsafe_allow_html=True,
                )
        return

    # Authenticated View: Map & Operational Feeds
    col_map, col_feed = st.columns([5, 4], gap="medium")

    with col_map:
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Live Map Overview</div>', unsafe_allow_html=True)
        _mini_map_preview(issues)

    with col_feed:
        if role == "admin":
            st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Recent Audit Events</div>', unsafe_allow_html=True)
            try:
                logs = get_audit_log(user, limit=7)
                if logs:
                    for log in logs[:7]:
                        st.markdown(
                            f'<div style="padding:8px 0;border-bottom:1px solid {TOKENS["border"]};font-size:13px">'
                            f'<strong>{log["user"]}</strong> '
                            f'<span style="color:{TOKENS["muted"]}">[{log["action"]}]</span> '
                            f'<span style="font-size:12px;color:{TOKENS["navy"]}">{log.get("detail","")}</span>'
                            f'<span style="float:right;color:{TOKENS["muted"]};font-size:11px">{relative_time(log["timestamp"])}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    empty_state("No recent activity", "Audit events will appear here.")
            except Exception:
                st.info("No audit data available.")

        elif role == "officer":
            high_unassigned = [i for i in open_issues if i["severity_label"] == "High" and not i.get("assigned_to")]
            st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Unassigned High-Priority Issues</div>', unsafe_allow_html=True)
            if high_unassigned:
                for iss in high_unassigned[:5]:
                    c_txt, c_btn = st.columns([3, 1])
                    with c_txt:
                        st.markdown(
                            f'<div style="padding:6px 0;font-size:14px">'
                            f'<strong>#{iss["id"]}</strong> {ISSUE_LABELS.get(iss["type"], iss["type"])} — {iss["area"]}<br>'
                            f'<span style="font-size:12px;color:{TOKENS["muted"]}">Reported {relative_time(iss["created_at"])}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with c_btn:
                        if st.button("Inspect", key=f"dash_inspect_{iss['id']}", use_container_width=True):
                            open_issue_dialog(iss["id"])
                    st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]};margin-bottom:4px"></div>', unsafe_allow_html=True)
            else:
                empty_state("All High Priorities Allocated", "No unassigned high-severity items in queue.")

        elif role == "citizen":
            st.markdown(f'<div style="font-size:16px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Your Active Submissions</div>', unsafe_allow_html=True)
            if open_issues:
                for iss in open_issues[:5]:
                    c_txt, c_btn = st.columns([3, 1])
                    with c_txt:
                        st.markdown(
                            f'<div style="padding:6px 0;font-size:14px">'
                            f'<strong>#{iss["id"]}</strong> {ISSUE_LABELS.get(iss["type"], iss["type"])} — {iss["area"]}<br>'
                            f'{status_badge(iss["status"])} <span style="font-size:12px;color:{TOKENS["muted"]};margin-left:6px">{relative_time(iss["created_at"])}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with c_btn:
                        if st.button("Details", key=f"dash_cit_inspect_{iss['id']}", use_container_width=True):
                            open_issue_dialog(iss["id"])
                    st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]};margin-bottom:4px"></div>', unsafe_allow_html=True)
            else:
                empty_state("No Active Reports", "You have no open reports currently.")

    # ── Top 5 Priority Issues ─────────────────────────────────────────────────
    st.markdown('<div style="margin-top:2rem"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:18px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Highest Priority Operational Work Orders</div>', unsafe_allow_html=True)

    top5 = sorted(open_issues, key=lambda x: -x["priority"])[:5]
    if top5:
        # Header
        h1, h2, h3, h4, h5, h6 = st.columns([0.6, 2.5, 1.2, 1.2, 1.5, 1.2])
        for col, title in zip([h1, h2, h3, h4, h5, h6], ["#", "Hazard & Area", "Severity", "Status", "Reported", "Action"]):
            with col:
                st.markdown(
                    f'<div style="font-size:11px;font-weight:700;color:{TOKENS["muted"]};'
                    f'text-transform:uppercase;border-bottom:2px solid {TOKENS["border"]};padding-bottom:4px">{title}</div>',
                    unsafe_allow_html=True,
                )

        for iss in top5:
            c1, c2, c3, c4, c5, c6 = st.columns([0.6, 2.5, 1.2, 1.2, 1.5, 1.2])
            with c1:
                st.markdown(f'<span style="font-size:14px;color:{TOKENS["muted"]};font-weight:600">#{iss["id"]}</span>', unsafe_allow_html=True)
            with c2:
                type_lbl = ISSUE_LABELS.get(iss["type"], iss["type"])
                st.markdown(
                    f'<span style="font-size:14px;font-weight:600;color:{TOKENS["navy"]}">{type_lbl}</span>'
                    f'<br><span style="font-size:12px;color:{TOKENS["muted"]}">{iss.get("area","—")} · Priority <strong>{iss["priority"]:.2f}</strong></span>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(severity_badge(iss["severity_label"]), unsafe_allow_html=True)
            with c4:
                st.markdown(status_badge(iss["status"]), unsafe_allow_html=True)
            with c5:
                st.markdown(f'<span style="font-size:13px;color:{TOKENS["muted"]}">{relative_time(iss["created_at"])}</span>', unsafe_allow_html=True)
            with c6:
                if st.button("View", key=f"top5_btn_{iss['id']}", use_container_width=True):
                    open_issue_dialog(iss["id"])

            st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]};margin:4px 0"></div>', unsafe_allow_html=True)
    else:
        empty_state("No open issues", "All municipal hazards have been inspected and resolved.")
