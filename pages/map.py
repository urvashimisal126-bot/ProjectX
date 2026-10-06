"""Live Map page — interactive Folium map with clustering, heatmaps, layer switches, and backend RBAC."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

from core.auth import current_user
from core.config import DEFAULT_LAT, DEFAULT_LON, DEFAULT_ZOOM, ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
from core.db import get_map_issues
from core.mapkit import build_map, SEV_MARKER_COLORS
from ui.components import page_header, empty_state
from ui.theme import TOKENS


def render() -> None:
    user = current_user()

    page_header("Live Map", "Real-time interactive geospatial monitor for municipal infrastructure hazards.", live=True)

    # ── Top Filter Bar ────────────────────────────────────────────────────────
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 2])
    with f_col1:
        sel_type = st.multiselect(
            "Hazard Type",
            options=ISSUE_CLASSES,
            format_func=lambda x: ISSUE_LABELS.get(x, x),
            key="live_map_type_filter",
        )
    with f_col2:
        sel_sev = st.multiselect(
            "Severity",
            options=["High", "Medium", "Low"],
            key="live_map_sev_filter",
        )
    with f_col3:
        sel_status = st.multiselect(
            "Status",
            options=["reported", "assigned", "fixed"],
            key="live_map_status_filter",
        )
    with f_col4:
        sel_area = st.selectbox(
            "Area Filter",
            options=["All Areas"] + INDORE_AREAS,
            index=0,
            key="live_map_area_filter",
        )

    # ── Map Control Options Bar ───────────────────────────────────────────────
    c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns([2, 2, 2, 2, 2])
    with c_col1:
        cluster_toggle = st.toggle("Cluster Markers", value=False, key="map_cluster_toggle")
    with c_col2:
        heatmap_toggle = st.toggle("Priority Heatmap", value=False, key="map_heat_toggle")
    with c_col3:
        show_fixed_toggle = st.toggle("Show Fixed", value=True, key="map_fixed_toggle")
    with c_col4:
        satellite_toggle = st.toggle("Satellite Layer", value=True, key="map_sat_toggle")
    with c_col5:
        simple_view_toggle = st.toggle("Simple Scatter View", value=False, key="map_simple_toggle")

    # ── Load data via backend RBAC ────────────────────────────────────────────
    filters = {}
    if sel_type:
        filters["type"] = sel_type
    if sel_sev:
        filters["severity_label"] = sel_sev
    if sel_status:
        filters["status"] = sel_status
    if sel_area and sel_area != "All Areas":
        filters["area"] = sel_area

    issues = get_map_issues(user, filters)

    st.markdown(
        f'<div style="font-size:12px;color:{TOKENS["muted"]};margin-bottom:0.75rem">'
        f'Displaying <strong>{len(issues)}</strong> geotagged hazards across Indore · '
        f'<span style="color:{TOKENS["deep_teal"]}">Layer control in top-right of map</span></div>',
        unsafe_allow_html=True,
    )

    if not issues:
        empty_state("No hazards match filters", "Try selecting different hazard types, severities, or areas.")
        return

    # ── Fallback Simple View (Plotly Scatter) ──────────────────────────────────
    if simple_view_toggle:
        st.info("Showing lightweight coordinate scatter view.")
        df_map = pd.DataFrame(issues)
        df_map["label"] = df_map["type"].map(lambda x: ISSUE_LABELS.get(x, x))
        fig = px.scatter(
            df_map,
            x="lon",
            y="lat",
            color="severity_label",
            size="priority",
            hover_name="label",
            hover_data={"lat": ":.4f", "lon": ":.4f", "area": True, "status": True, "priority": ":.2f"},
            color_discrete_map=SEV_MARKER_COLORS,
            title="UrbanLens Issues Geographic Distribution",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#F5F7FA",
            height=600,
            font=dict(family="Inter", color="#0B2545"),
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    # ── Render Interactive Folium Map ─────────────────────────────────────────
    try:
        # Check auto-cluster rule (>40 items)
        auto_cluster = cluster_toggle or (len(issues) > 40)

        # Center map
        avg_lat = sum(i["lat"] for i in issues) / len(issues) if issues else DEFAULT_LAT
        avg_lon = sum(i["lon"] for i in issues) / len(issues) if issues else DEFAULT_LON

        folium_map = build_map(
            issues=issues,
            center=(avg_lat, avg_lon),
            zoom=DEFAULT_ZOOM,
            cluster=auto_cluster,
            show_heatmap=heatmap_toggle,
            show_fixed=show_fixed_toggle,
            enable_satellite=satellite_toggle,
            compact=False,
        )

        map_output = st_folium(
            folium_map,
            width="100%",
            height=660,
            key="urbanlens_live_folium_map",
            returned_objects=["last_object_clicked", "last_clicked"],
        )

        # Handle marker interaction
        if map_output and map_output.get("last_object_clicked"):
            clicked = map_output["last_object_clicked"]
            c_lat = clicked.get("lat")
            c_lng = clicked.get("lng")
            if c_lat and c_lng:
                # Find closest issue
                matched = min(
                    issues,
                    key=lambda i: (i["lat"] - c_lat) ** 2 + (i["lon"] - c_lng) ** 2,
                )
                st.markdown(
                    f"""
                    <div style="background:#fff;border:1px solid {TOKENS['border']};border-radius:8px;padding:0.75rem 1rem;margin-top:0.75rem;display:flex;justify-content:space-between;align-items:center">
                      <div>
                        <strong>Selected: #{matched['id']} {ISSUE_LABELS.get(matched['type'], matched['type'])}</strong> — {matched.get('area','Unknown')} · Priority {matched.get('priority',0):.2f}
                      </div>
                      <a href="javascript:void(0)" onclick="" style="color:{TOKENS['deep_teal']};font-weight:600;text-decoration:none">View details in Issue Detail tab</a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    except Exception as exc:
        st.warning(f"Interactive Leaflet map encountered a rendering error: {exc}. Displaying fallback view.")
        df_map = pd.DataFrame(issues)
        fig = px.scatter(df_map, x="lon", y="lat", color="severity_label", color_discrete_map=SEV_MARKER_COLORS)
        st.plotly_chart(fig, use_container_width=True)
