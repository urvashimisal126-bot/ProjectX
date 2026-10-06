"""
UrbanLens MapKit — Free, Key-less Interactive Geospatial Map Engine.
Built with Folium (Leaflet) + CARTO / OpenStreetMap / Esri tiles.
No paid APIs, zero tracking, legal tile attributions.
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
from pathlib import Path
from PIL import Image

import folium
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap, MeasureControl
from branca.element import Element, MacroElement, Template

from core.config import (
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_ZOOM, ISSUE_LABELS,
    ENABLE_SATELLITE_LAYER, WARDS_GEOJSON_PATH
)
from ui.theme import TOKENS
from ui.components import relative_time

# ─── Color mappings ───────────────────────────────────────────────────────────
SEV_MARKER_COLORS = {
    "High":   "#C8372D",
    "Medium": "#E08A1E",
    "Low":    "#2E9E6B",
}
STATUS_FIXED_COLOR = "#1B9C85"

# ─── Tile Providers & Attributions ────────────────────────────────────────────
TILES_CONFIG = {
    "positron": {
        "name": "Light (CARTO Positron)",
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        "subdomains": "abcd",
        "max_zoom": 20,
    },
    "osm": {
        "name": "Streets (OpenStreetMap)",
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        "subdomains": "abc",
        "max_zoom": 19,
    },
    "dark": {
        "name": "Dark (CARTO Dark Matter)",
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "attr": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        "subdomains": "abcd",
        "max_zoom": 20,
    },
    "satellite": {
        "name": "Satellite (Esri Imagery)",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
        "subdomains": "abc",
        "max_zoom": 19,
    },
}


# ─── Thumbnail Data URI Generator (Cached in memory) ──────────────────────────
_THUMB_CACHE: dict[str, str] = {}


def _get_thumbnail_data_uri(image_path: str, max_w: int = 140) -> str:
    """Return a base64 JPEG data URI for popup thumbnails (max 140px wide)."""
    if not image_path or not Path(image_path).exists():
        return ""

    if image_path in _THUMB_CACHE:
        return _THUMB_CACHE[image_path]

    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if w > max_w:
                ratio = max_w / float(w)
                new_h = max(int(h * ratio), 1)
                img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            data_uri = f"data:image/jpeg;base64,{b64_str}"
            _THUMB_CACHE[image_path] = data_uri
            return data_uri
    except Exception:
        return ""


# ─── Popup HTML Builder ───────────────────────────────────────────────────────

def _build_popup_html(issue: dict) -> str:
    """Generate a clean, XSS-safe popup HTML card matching the UrbanLens theme."""
    iid = issue.get("id", 0)
    raw_type = issue.get("type", "hazard")
    type_label = html.escape(ISSUE_LABELS.get(raw_type, raw_type))
    sev_label = html.escape(str(issue.get("severity_label", "Low")))
    status_label = html.escape(str(issue.get("status", "reported")).capitalize())
    prio = float(issue.get("priority", 0.0))
    area = html.escape(str(issue.get("area") or "Unknown Area"))
    report_count = int(issue.get("report_count", 1))
    rel_time = html.escape(relative_time(issue.get("created_at", "")))

    thumb_uri = _get_thumbnail_data_uri(issue.get("image_path", ""))
    thumb_html = ""
    if thumb_uri:
        thumb_html = f'<div style="text-align:center;margin-bottom:8px"><img src="{thumb_uri}" style="max-width:100%;max-height:100px;border-radius:4px;border:1px solid #E3E8EF;object-fit:cover"/></div>'

    sev_color = SEV_MARKER_COLORS.get(sev_label, "#2E9E6B")
    status_color = "#1B9C85" if status_label.lower() == "fixed" else ("#2F6FB5" if status_label.lower() == "assigned" else "#5B6B7F")

    return f"""
    <div style="font-family:'Inter',system-ui,sans-serif;font-size:12px;color:#0B2545;width:240px;padding:4px">
      {thumb_html}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <span style="font-weight:700;font-size:13px;color:#0B2545">#{iid} {type_label}</span>
        <span style="background:{status_color}22;color:{status_color};border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700;text-transform:uppercase">{status_label}</span>
      </div>
      <div style="font-size:11px;color:#5B6B7F;margin-bottom:6px">{area} · {rel_time}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;background:#F5F7FA;padding:4px 8px;border-radius:4px;margin-bottom:8px">
        <span>Severity: <strong style="color:{sev_color}">{sev_label}</strong></span>
        <span>Priority: <strong>{prio:.2f}</strong></span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;font-size:11px;color:#5B6B7F">
        <span>Reports: <strong>{report_count}</strong></span>
        <a href="javascript:window.parent.postMessage({{type:'open_issue',id:{iid}}},'*');"
           style="background:#136F63;color:#FFFFFF;text-decoration:none;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600"
           target="_self">View Details</a>
      </div>
    </div>
    """


# ─── Custom Floating Legend ───────────────────────────────────────────────────

def _add_legend(m: folium.Map) -> None:
    """Add a responsive floating HTML legend to the top-right corner."""
    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 999;
        background: white;
        padding: 12px 14px;
        border-radius: 8px;
        border: 1px solid #E3E8EF;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 11px;
        color: #0B2545;
        line-height: 1.5;
        max-width: 170px;
    ">
      <div style="font-weight:700;font-size:12px;margin-bottom:6px;border-bottom:1px solid #E3E8EF;padding-bottom:3px">Map Legend</div>
      <div style="margin-bottom:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#C8372D;margin-right:6px"></span>High Severity</div>
      <div style="margin-bottom:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#E08A1E;margin-right:6px"></span>Medium Severity</div>
      <div style="margin-bottom:4px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#2E9E6B;margin-right:6px"></span>Low Severity</div>
      <div style="margin-bottom:6px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#1B9C85;margin-right:6px"></span>Fixed / Resolved</div>
      <div style="font-size:10px;color:#5B6B7F;border-top:1px solid #E3E8EF;padding-top:4px">
        Marker size = Priority score<br>
        Tiles &copy; OpenStreetMap/CARTO
      </div>
    </div>
    """
    m.get_root().html.add_child(Element(legend_html))


# ─── Main Map Builder ─────────────────────────────────────────────────────────

def build_map(
    issues: list[dict],
    center: tuple[float, float] = (DEFAULT_LAT, DEFAULT_LON),
    zoom: int = DEFAULT_ZOOM,
    cluster: bool = False,
    show_heatmap: bool = False,
    show_fixed: bool = True,
    enable_satellite: bool = True,
    compact: bool = False,
) -> folium.Map:
    """
    Build a production-grade Folium map for UrbanLens.
    Supports switchable CARTO/OSM/Satellite layers, marker clustering,
    heatmaps, XSS-safe popup cards, and corner legend.
    """
    # Initialize base map with default Positron
    pos = TILES_CONFIG["positron"]
    m = folium.Map(
        location=list(center),
        zoom_start=zoom,
        tiles=pos["url"],
        attr=pos["attr"],
        name=pos["name"],
        control_scale=True,
    )

    # Add Streets layer (OpenStreetMap)
    osm = TILES_CONFIG["osm"]
    folium.TileLayer(
        tiles=osm["url"],
        attr=osm["attr"],
        name=osm["name"],
        subdomains=osm["subdomains"],
        max_zoom=osm["max_zoom"],
    ).add_to(m)

    # Add Dark Matter layer
    dark = TILES_CONFIG["dark"]
    folium.TileLayer(
        tiles=dark["url"],
        attr=dark["attr"],
        name=dark["name"],
        subdomains=dark["subdomains"],
        max_zoom=dark["max_zoom"],
    ).add_to(m)

    # Optional Satellite Layer
    if enable_satellite and ENABLE_SATELLITE_LAYER:
        sat = TILES_CONFIG["satellite"]
        folium.TileLayer(
            tiles=sat["url"],
            attr=sat["attr"],
            name=sat["name"],
            subdomains=sat["subdomains"],
            max_zoom=sat["max_zoom"],
        ).add_to(m)

    # Add Optional GeoJSON Ward layer if file exists
    if Path(WARDS_GEOJSON_PATH).exists():
        try:
            with open(WARDS_GEOJSON_PATH, "r", encoding="utf-8") as f:
                ward_data = json.load(f)
            folium.GeoJson(
                ward_data,
                name="Municipal Wards",
                style_function=lambda x: {
                    "fillColor": "#136F63",
                    "color": "#0B2545",
                    "weight": 1.5,
                    "fillOpacity": 0.08,
                },
                tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Ward:"]),
            ).add_to(m)
        except Exception:
            pass

    # Filter out fixed issues if toggle is off
    active_issues = issues if show_fixed else [i for i in issues if str(i.get("status", "")).lower() != "fixed"]

    # Target container for markers (Cluster vs direct Map)
    container = MarkerCluster(name="Clustered Issues").add_to(m) if cluster else m

    # Plot Circle Markers
    heat_data: list[list[float]] = []

    for issue in active_issues:
        lat = issue.get("lat")
        lon = issue.get("lon")
        if lat is None or lon is None:
            continue

        sev = str(issue.get("severity_label", "Low"))
        status = str(issue.get("status", "reported")).lower()
        priority = float(issue.get("priority", 0.5))

        # Color: Fixed takes teal color; otherwise severity color
        color = STATUS_FIXED_COLOR if status == "fixed" else SEV_MARKER_COLORS.get(sev, "#2E9E6B")

        # Scaled radius from priority (6px to 16px)
        radius = min(max(int(6 + priority * 7), 6), 16)

        # Hover tooltip
        raw_type = issue.get("type", "hazard")
        type_str = ISSUE_LABELS.get(raw_type, raw_type)
        tooltip_txt = f"#{issue.get('id')} {type_str} · {sev} · {status.capitalize()}"

        # Popup card
        popup_html = _build_popup_html(issue)
        popup = folium.Popup(popup_html, max_width=280)

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color="#FFFFFF",
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.90,
            popup=popup,
            tooltip=tooltip_txt,
        ).add_to(container)

        # Heatmap weight point
        heat_data.append([lat, lon, max(priority, 0.2)])

    # Optional HeatMap Layer
    if show_heatmap and heat_data:
        HeatMap(
            heat_data,
            name="Priority Heatmap",
            min_opacity=0.3,
            radius=18,
            blur=15,
            gradient={"0.2": "#6CC48A", "0.5": "#E08A1E", "0.8": "#C8372D"},
        ).add_to(m)

    # Controls (omitted for compact preview)
    if not compact:
        folium.LayerControl(position="topright", collapsed=True).add_to(m)
        Fullscreen(position="topleft").add_to(m)
        MeasureControl(position="bottomleft", primary_length_unit="meters").add_to(m)
        _add_legend(m)

    # Fit bounds if points exist
    if active_issues:
        coords = [[i["lat"], i["lon"]] for i in active_issues if i.get("lat") and i.get("lon")]
        if len(coords) > 1:
            m.fit_bounds(coords, padding=(30, 30))

    return m
