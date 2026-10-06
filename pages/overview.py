"""Overview / Home page — role-personalised."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.auth import current_user
from core.db import list_issues, kpi_counts, sparkline_data, get_audit_log, has_permission
from ui.components import page_header, kpi_card, severity_badge, status_badge, relative_time, empty_state
from ui.theme import TOKENS


def _mini_map_preview(issues: list[dict]) -> None:
    """Render a compact folium map preview."""
    try:
        from core.mapkit import build_map
        from streamlit_folium import st_folium
        m = build_map(issues[:40], compact=True)
        st_folium(m, height=280, width="100%", returned_objects=[], key="overview_mini_map")
    except Exception as e:
        st.info(f"Map preview unavailable: {e}")


def render() -> None:
    user = current_user()
    role = user.get("role", "guest")

    page_header(
        "Overview",
        "Welcome to UrbanLens — your city infrastructure command centre.",
        live=True,
    )

    # ── KPI row ──────────────────────────────────────────────────────────────
    kpis = kpi_counts(user)
    spark = sparkline_data(14)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Open Issues", str(kpis["total"]), sparkline=spark)
    with k2:
        kpi_card("High Severity", str(kpis["high"]),
                 delta=f"{'Needs attention' if kpis['high'] > 3 else 'Under control'}",
                 delta_good=kpis["high"] <= 3)
    with k3:
        hours = kpis["avg_fix_hours"]
        kpi_card("Avg. Time to Fix", f"{hours}h" if hours else "—")
    with k4:
        kpi_card("Fixed This Week", str(kpis["fixed_week"]),
                 delta="this week", delta_good=True)

    st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

    # ── Role-specific content ─────────────────────────────────────────────────
    if role == "guest":
        # Public summary only
        issues = list_issues(user)
        col_map, col_sum = st.columns([3, 1])
        with col_map:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.5rem">Live Infrastructure Map</div>', unsafe_allow_html=True)
            _mini_map_preview(issues)
        with col_sum:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Summary</div>', unsafe_allow_html=True)
            by_type = {}
            for iss in issues:
                by_type[iss["type"]] = by_type.get(iss["type"], 0) + 1
            for t, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:6px 0;border-bottom:1px solid {TOKENS["border"]};'
                    f'font-size:13px"><span>{t.replace("_"," ").title()}</span>'
                    f'<strong>{cnt}</strong></div>',
                    unsafe_allow_html=True,
                )
        return

    # ── Logged-in users: top priority issues ─────────────────────────────────
    col_map, col_right = st.columns([2, 1])

    issues = list_issues(user)
    open_issues = [i for i in issues if i["status"] != "fixed"]

    with col_map:
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.5rem">Map Preview</div>', unsafe_allow_html=True)
        _mini_map_preview(issues)

    with col_right:
        if role == "admin":
            # Recent audit events
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Recent Activity</div>', unsafe_allow_html=True)
            try:
                logs = get_audit_log(user, limit=8)
                for log in logs[:8]:
                    st.markdown(
                        f'<div style="padding:6px 0;border-bottom:1px solid {TOKENS["border"]};font-size:12px">'
                        f'<strong>{log["user"]}</strong> '
                        f'<span style="color:{TOKENS["muted"]}">{log["action"]}</span>'
                        f'<span style="float:right;color:{TOKENS["muted"]}">{relative_time(log["timestamp"])}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                st.info("No audit data available.")
        elif role == "officer":
            # Unassigned High-priority issues
            high = [i for i in open_issues if i["severity_label"] == "High" and not i.get("assigned_to")]
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.75rem">Unassigned High-Priority</div>', unsafe_allow_html=True)
            if high:
                for iss in high[:5]:
                    st.markdown(
                        f'<div style="padding:6px 0;border-bottom:1px solid {TOKENS["border"]};font-size:13px">'
                        f'<strong>#{iss["id"]}</strong> {iss["type"].replace("_"," ").title()} '
                        f'— {iss["area"]} '
                        f'<span style="float:right">{severity_badge(iss["severity_label"])}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown("", unsafe_allow_html=True)
            else:
                empty_state("All clear", "No unassigned high-priority issues.")

    # ── Top 5 priority issues table ────────────────────────────────────────
    st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1.5rem 0 0.5rem">Top 5 Priority Issues</div>', unsafe_allow_html=True)
    top5 = sorted(open_issues, key=lambda x: -x["priority"])[:5]
    if top5:
        for iss in top5:
            c1, c2, c3, c4, c5 = st.columns([0.5, 2, 1.5, 1.5, 1.5])
            with c1:
                st.markdown(f'<span style="font-size:13px;color:{TOKENS["muted"]}">#{iss["id"]}</span>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<span style="font-size:13px;font-weight:600">{iss["type"].replace("_"," ").title()}</span><br><span style="font-size:11px;color:{TOKENS["muted"]}">{iss["area"]}</span>', unsafe_allow_html=True)
            with c3:
                st.markdown(severity_badge(iss["severity_label"]), unsafe_allow_html=True)
            with c4:
                st.markdown(status_badge(iss["status"]), unsafe_allow_html=True)
            with c5:
                st.markdown(f'<span style="font-size:12px;color:{TOKENS["muted"]}">{relative_time(iss["created_at"])}</span>', unsafe_allow_html=True)
            st.markdown(f'<div style="border-bottom:1px solid {TOKENS["border"]}"></div>', unsafe_allow_html=True)
    else:
        empty_state("No open issues", "Everything is up to date.")
