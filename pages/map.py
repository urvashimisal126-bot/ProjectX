"""Live Map page — full-width Folium map with filters."""
from __future__ import annotations

import streamlit as st

from core.auth import current_user
from core.config import DEFAULT_LAT, DEFAULT_LON, ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS
from core.db import list_issues
from ui.components import page_header, empty_state
from ui.theme import TOKENS


_SEV_COLOR = {"High": "#C8372D", "Medium": "#E08A1E", "Low": "#2E9E6B"}
_SEV_RADIUS = {"High": 12, "Medium": 9, "Low": 7}


def render() -> None:
    user = current_user()

    page_header("Live Map", "Real-time geotag view of all reported infrastructure issues.", live=True)

    # ── Filter sidebar ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            f'<div style="font-size:12px;font-weight:700;color:rgba(255,255,255,0.5);'
            f'text-transform:uppercase;letter-spacing:0.05em;margin:1rem 0 0.5rem">Map Filters</div>',
            unsafe_allow_html=True,
        )
        sel_type = st.multiselect(
            "Issue type",
            options=ISSUE_CLASSES,
            format_func=lambda x: ISSUE_LABELS.get(x, x),
            key="map_type_filter",
        )
        sel_sev = st.multiselect(
            "Severity",
            options=["High", "Medium", "Low"],
            key="map_sev_filter",
        )
        sel_status = st.multiselect(
            "Status",
            options=["reported", "assigned", "fixed"],
            key="map_status_filter",
        )

    # ── Load issues ───────────────────────────────────────────────────────────
    filters = {}
    if sel_type:    filters["type"] = sel_type
    if sel_sev:     filters["severity_label"] = sel_sev
    if sel_status:  filters["status"] = sel_status

    issues = list_issues(user, filters)
    geo_issues = [i for i in issues if i.get("lat") and i.get("lon")]

    st.markdown(
        f'<div style="font-size:13px;color:{TOKENS["muted"]};margin-bottom:0.75rem">'
        f'Showing <strong>{len(geo_issues)}</strong> geotagged issues'
        + (" (use filters to narrow down)" if len(issues) > len(geo_issues) else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    if not geo_issues:
        empty_state("No issues on map", "No geotagged issues match the current filters.")
        return

    # ── Build Folium map ──────────────────────────────────────────────────────
    try:
        import folium  # noqa: PLC0415
        from streamlit_folium import st_folium  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415
        import base64  # noqa: PLC0415
        import os  # noqa: PLC0415

        m = folium.Map(
            location=[DEFAULT_LAT, DEFAULT_LON],
            zoom_start=12,
            tiles="CartoDB positron",
        )

        for iss in geo_issues:
            color = _SEV_COLOR.get(iss["severity_label"], "#5B6B7F")
            radius = _SEV_RADIUS.get(iss["severity_label"], 8)

            # Thumbnail HTML
            img_html = ""
            img_path = iss.get("image_path", "")
            if img_path and Path(img_path).exists():
                try:
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    img_html = f'<img src="data:image/jpeg;base64,{b64}" width="200" style="border-radius:4px;margin-bottom:8px"><br>'
                except Exception:
                    pass

            popup_html = f"""
            <div style="font-family:sans-serif;min-width:220px">
              {img_html}
              <strong style="font-size:14px">#{iss['id']} {iss['type'].replace('_',' ').title()}</strong><br>
              <span style="color:#5B6B7F;font-size:12px">{iss.get('area','')}</span><br><br>
              <table style="font-size:12px;width:100%">
                <tr><td style="color:#5B6B7F">Severity</td><td><strong>{iss['severity_label']}</strong></td></tr>
                <tr><td style="color:#5B6B7F">Priority</td><td><strong>{iss['priority']:.3f}</strong></td></tr>
                <tr><td style="color:#5B6B7F">Status</td><td><strong>{iss['status'].capitalize()}</strong></td></tr>
              </table>
            </div>
            """

            folium.CircleMarker(
                location=[iss["lat"], iss["lon"]],
                radius=radius,
                color="#fff",
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f'#{iss["id"]} {iss["type"]} — {iss["severity_label"]}',
            ).add_to(m)

        # Legend
        legend_html = """
        <div style="position:fixed;bottom:30px;right:30px;background:#fff;
                    border:1px solid #E3E8EF;border-radius:8px;padding:12px;
                    font-family:sans-serif;font-size:12px;z-index:9999">
          <div style="font-weight:700;margin-bottom:6px;color:#0B2545">Severity</div>
          <div><span style="display:inline-block;width:12px;height:12px;background:#C8372D;border-radius:50%;margin-right:6px"></span>High</div>
          <div><span style="display:inline-block;width:10px;height:10px;background:#E08A1E;border-radius:50%;margin-right:6px"></span>Medium</div>
          <div><span style="display:inline-block;width:8px;height:8px;background:#2E9E6B;border-radius:50%;margin-right:6px"></span>Low</div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        map_data = st_folium(m, height=560, use_container_width=True, returned_objects=["last_object_clicked"])

        # Issue detail navigation on click
        clicked = (map_data or {}).get("last_object_clicked")
        if clicked:
            click_lat = clicked.get("lat")
            click_lng = clicked.get("lng")
            if click_lat and click_lng:
                # Find closest issue
                from core.geo import haversine  # noqa: PLC0415
                closest = min(
                    geo_issues,
                    key=lambda i: haversine(click_lat, click_lng, i["lat"], i["lon"]),
                )
                st.info(f"Clicked near Issue #{closest['id']} — {closest['type'].replace('_',' ').title()} in {closest['area']}.")
                if st.button(f"View Issue #{closest['id']} Detail", key="map_view_detail"):
                    st.session_state["detail_issue_id"] = closest["id"]
                    st.session_state["goto_page"] = "detail"
                    st.rerun()

    except ImportError as e:
        st.error(f"Map library not available: {e}. Run: pip install folium streamlit-folium")
