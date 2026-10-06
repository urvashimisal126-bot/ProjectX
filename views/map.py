"""
Live Map page — Interactive Folium geospatial monitoring engine.
100% key-less tiles, clustering, priority heatmaps, layer switches, and backend RBAC.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

from core.auth import current_user
try:
    from core.config import DEFAULT_LAT, DEFAULT_LON, DEFAULT_ZOOM, ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
except ImportError:
    from core.config import DEFAULT_LAT, DEFAULT_LON, ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
    DEFAULT_ZOOM = 12
from core.db import get_map_issues
from core.mapkit import build_map, SEV_MARKER_COLORS
from ui.components import page_header, empty_state
from ui.theme import TOKENS
from views.issue_detail import open_issue_dialog


def render() -> None:
    user = current_user()

    page_header(
        "Live Map",
        "Geospatial monitoring across Indore — severity colored, priority scaled, and 100% free tiles.",
        live=True,
    )

    # ── Filters Bar ───────────────────────────────────────────────────────────
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

    # ── Map Controls Bar ──────────────────────────────────────────────────────
    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    with c_col1:
        cluster_toggle = st.toggle("Cluster Markers", value=False, key="map_cluster_toggle")
    with c_col2:
        heatmap_toggle = st.toggle("Priority Heatmap", value=False, key="map_heat_toggle")
    with c_col3:
        show_fixed_toggle = st.toggle("Show Fixed Hazards", value=True, key="map_fixed_toggle")
    with c_col4:
        satellite_toggle = st.toggle("Satellite Imagery", value=True, key="map_sat_toggle")

    # ── Query Data with Backend RBAC ──────────────────────────────────────────
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
        f"""
        <div style="font-size:13px;color:{TOKENS['muted']};margin:0.5rem 0 0.85rem 0">
          Displaying <strong>{len(issues)}</strong> geotagged infrastructure items ·
          <span style="color:{TOKENS['teal_deep']}">Click any marker for details and photo preview</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not issues:
        empty_state("No hazards match filter criteria", "Adjust the filters above to explore other municipal areas.")
        return

    # ── Render Folium Map ─────────────────────────────────────────────────────
    try:
        auto_cluster = cluster_toggle or (len(issues) > 50)
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
            returned_objects=["last_object_clicked"],
        )

        # Marker Interaction Card
        if map_output and map_output.get("last_object_clicked"):
            clicked = map_output["last_object_clicked"]
            c_lat = clicked.get("lat")
            c_lng = clicked.get("lng")
            if c_lat and c_lng:
                matched = min(
                    issues,
                    key=lambda i: (i["lat"] - c_lat) ** 2 + (i["lon"] - c_lng) ** 2,
                )
                type_lbl = ISSUE_LABELS.get(matched['type'], matched['type'])
                st.markdown(
                    f"""
                    <div style="background:#FFFFFF;border:1px solid {TOKENS['border']};
                                border-radius:10px;padding:1rem 1.25rem;margin-top:1rem;
                                display:flex;justify-content:space-between;align-items:center;
                                box-shadow:0 2px 6px rgba(11,37,69,0.06)">
                      <div>
                        <div style="font-size:15px;font-weight:700;color:{TOKENS['navy']}">
                          Selected: #{matched['id']} {type_lbl}
                        </div>
                        <div style="font-size:13px;color:{TOKENS['muted']}">
                          {matched.get('area', 'Unknown Area')} · Priority: <strong>{matched.get('priority',0):.3f}</strong> · Status: <strong>{matched.get('status','').capitalize()}</strong>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Inspect Full Details & AI Assessment", key=f"map_inspect_{matched['id']}", type="primary"):
                    open_issue_dialog(matched["id"])

    except Exception as exc:
        st.warning(f"Map rendering error: {exc}. Displaying scatter preview.")
        df_map = pd.DataFrame(issues)
        fig = px.scatter(df_map, x="lon", y="lat", color="severity_label", color_discrete_map=SEV_MARKER_COLORS)
        st.plotly_chart(fig, use_container_width=True)
