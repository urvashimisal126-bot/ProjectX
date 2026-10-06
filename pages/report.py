"""Report an Issue page."""
from __future__ import annotations

import os
import io
import json
import uuid
from pathlib import Path

import streamlit as st
from PIL import Image

from core.auth import current_user, require_role
from core.config import (
    DEFAULT_LAT, DEFAULT_LON, ISSUE_CLASSES, ISSUE_LABELS,
    UPLOAD_DIR, DEFAULT_CONF_THRESHOLD, DETECTOR, GEMINI_MODEL,
    GEMINI_DEFAULT_CONFIDENCE
)
from core.detect import detect_image, detect_video, DEMO_MODE
from core.geo import extract_gps, get_location_type
from core.score import compute_severity, compute_priority, severity_breakdown
from core.db import create_issue, has_permission
from core.dedupe import find_duplicate, merge_into
from core.audit import log_audit
from core.notify import send_high_severity_alert
from ui.components import page_header, severity_badge, ai_assessment_card
from ui.theme import TOKENS


def _save_upload(uploaded_file) -> str:
    """Save uploaded file and return the path."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = Path(uploaded_file.name).suffix.lower() or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return fpath


def render() -> None:
    require_role(["admin", "officer", "citizen"])
    user = current_user()

    page_header("Report Issue", "Upload a photo or video — hybrid AI will detect, classify, and assess the hazard.")

    if DEMO_MODE:
        st.warning(
            "**Demo mode:** YOLO model weights missing from models/best.pt. Using Gemini and synthetic bounding boxes.",
            icon="⚠️",
        )

    uploaded = st.file_uploader(
        "Drag and drop an image or short video",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "avi"],
        key="report_uploader",
        help="Supported: JPEG, PNG, WebP, MP4, MOV, AVI",
    )

    if not uploaded:
        st.markdown(
            f'<div style="text-align:center;padding:3rem;color:{TOKENS["muted"]};'
            f'border:2px dashed {TOKENS["border"]};border-radius:10px;margin-top:1rem">'
            f'<div style="font-size:32px;margin-bottom:0.5rem;color:{TOKENS["border"]}">▲</div>'
            f'<div style="font-weight:600">Drop your file here or click to browse</div>'
            f'<div style="font-size:12px;margin-top:4px">Images up to 100 MB · Short video clips</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Save file ─────────────────────────────────────────────────────────────
    file_path = _save_upload(uploaded)
    is_video = uploaded.type.startswith("video")

    # ── Preview ────────────────────────────────────────────────────────────────
    col_preview, col_analysis = st.columns([1, 1])

    with col_preview:
        st.markdown(f'<div style="font-size:13px;font-weight:700;color:{TOKENS["muted"]};margin-bottom:0.5rem">ORIGINAL</div>', unsafe_allow_html=True)
        if is_video:
            st.video(file_path)
        else:
            st.image(file_path, use_container_width=True)

    # ── Advanced settings ─────────────────────────────────────────────────────
    can_configure_detector = (user or {}).get("role") in ["admin", "officer"]
    detector_mode = DETECTOR

    with st.expander("Advanced settings & AI configuration", expanded=False):
        if can_configure_detector:
            mode_options = ["hybrid", "yolo", "gemini"]
            curr_idx = mode_options.index(DETECTOR) if DETECTOR in mode_options else 0
            detector_mode = st.selectbox(
                "Detection Engine Mode",
                options=mode_options,
                index=curr_idx,
                help="Hybrid uses YOLO first and Gemini for assessment; Gemini uses vision reasoning; YOLO runs local models.",
                format_func=lambda m: f"{m.upper()} mode" + (" (Recommended)" if m == "hybrid" else ""),
            )
        else:
            st.markdown(f"<div style='font-size:12px;color:{TOKENS['muted']}'>Active Detector: <strong>{DETECTOR.upper()}</strong></div>", unsafe_allow_html=True)

        conf_threshold = st.slider(
            "Confidence threshold",
            min_value=0.10, max_value=0.90,
            value=DEFAULT_CONF_THRESHOLD,
            step=0.05,
            format="%.2f",
        )
        selected_classes = st.multiselect(
            "Detect only these types",
            options=ISSUE_CLASSES,
            default=ISSUE_CLASSES,
            format_func=lambda x: ISSUE_LABELS.get(x, x),
        )

    # ── Analyse button ────────────────────────────────────────────────────────
    if st.button("Analyse with AI", key="analyse_btn", type="primary"):
        with st.spinner(f"Running {detector_mode.upper()} detection & Gemini assessment…"):
            try:
                if is_video:
                    result = detect_video(file_path, conf_threshold=conf_threshold, class_list=selected_classes or ISSUE_CLASSES, mode=detector_mode, actor=user)
                    if result:
                        st.session_state["report_result"] = result[0]
                    else:
                        st.session_state["report_result"] = None
                else:
                    result = detect_image(file_path, conf_threshold=conf_threshold, class_list=selected_classes or ISSUE_CLASSES, mode=detector_mode, actor=user)
                    st.session_state["report_result"] = result
            except Exception as e:
                st.error(f"Detection pipeline error: {e}")
                return

        st.session_state["report_file_path"] = file_path
        st.session_state["report_is_video"] = is_video
        st.session_state["report_detector_used"] = detector_mode

    result = st.session_state.get("report_result")
    file_path_saved = st.session_state.get("report_file_path", file_path)

    if result is None:
        return

    with col_analysis:
        st.markdown(f'<div style="font-size:13px;font-weight:700;color:{TOKENS["muted"]};margin-bottom:0.5rem">DETECTION RESULT ({result.detector_used.upper()})</div>', unsafe_allow_html=True)
        st.image(result.annotated_image, use_container_width=True)

    # ── AI Assessment Card ────────────────────────────────────────────────────
    assess_dict = result.assessment.model_dump() if result.assessment else None
    ai_assessment_card(assess_dict, model_name=f"Google {GEMINI_MODEL}")

    if not result.detections:
        st.info("No infrastructure issues detected in this file. Try adjusting the confidence threshold or detector mode.")
        return

    # ── Detection breakdown ───────────────────────────────────────────────────
    st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1.25rem 0 0.5rem">Detected Hazards</div>', unsafe_allow_html=True)

    # Determine primary detection
    primary = max(result.detections, key=lambda d: d.confidence if d.confidence is not None else GEMINI_DEFAULT_CONFIDENCE)
    detect_count = len(result.detections)

    eff_conf = primary.confidence if primary.confidence is not None else GEMINI_DEFAULT_CONFIDENCE
    score, label = compute_severity(primary.area_ratio, primary.confidence, detect_count)
    breakdown = severity_breakdown(
        primary.area_ratio, primary.confidence, detect_count, "default", 1
    )

    dcols = st.columns(len(result.detections))
    for i, det in enumerate(result.detections):
        with dcols[i]:
            s, l = compute_severity(det.area_ratio, det.confidence, detect_count)
            conf_display = f"{det.confidence:.0%}" if det.confidence is not None else "Estimated (50%)"
            src_badge = f'<span style="font-size:10px;background:#edf3fb;color:#2F6FB5;padding:2px 6px;border-radius:4px;font-weight:600;margin-left:4px">{det.source.upper()}</span>'

            st.markdown(
                f'<div style="background:#fff;border:1px solid {TOKENS["border"]};'
                f'border-radius:8px;padding:0.75rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span style="font-size:12px;font-weight:700;color:{TOKENS["muted"]};text-transform:uppercase">{ISSUE_LABELS.get(det.class_name, det.class_name)}</span>'
                f'{src_badge}'
                f'</div>'
                f'<div style="font-size:18px;font-weight:700;color:{TOKENS["navy"]};margin:4px 0">{conf_display}</div>'
                f'<div style="font-size:11px;color:{TOKENS["muted"]}">Confidence · {severity_badge(l)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Location ──────────────────────────────────────────────────────────────
    st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1.25rem 0 0.5rem">Geotag & Location Picker</div>', unsafe_allow_html=True)

    gps = extract_gps(file_path_saved) if not st.session_state.get("report_is_video") else None

    # Default lat/lon
    if "report_lat" not in st.session_state:
        st.session_state["report_lat"] = gps[0] if gps else DEFAULT_LAT
    if "report_lon" not in st.session_state:
        st.session_state["report_lon"] = gps[1] if gps else DEFAULT_LON

    if gps:
        st.success(f"GPS extracted from photo metadata: {gps[0]:.5f}, {gps[1]:.5f}")
    else:
        st.info("Click anywhere on the interactive map below or enter coordinates manually to set the hazard pin.")

    # Location Inputs
    c_lat, c_lon = st.columns(2)
    with c_lat:
        lat_val = st.number_input(
            "Latitude",
            value=float(st.session_state["report_lat"]),
            format="%.5f",
            key="report_lat_input",
        )
    with c_lon:
        lon_val = st.number_input(
            "Longitude",
            value=float(st.session_state["report_lon"]),
            format="%.5f",
            key="report_lon_input",
        )

    # Mini Click-to-Pick Folium Map
    import folium
    from streamlit_folium import st_folium
    from core.geo import get_location_type, validate_coordinates, reverse_geocode_area

    picker_map = folium.Map(
        location=[lat_val, lon_val],
        zoom_start=14,
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr='&copy; OpenStreetMap contributors &copy; CARTO',
    )
    folium.Marker(
        [lat_val, lon_val],
        popup="Hazard Location",
        tooltip="Selected Hazard Pin",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(picker_map)

    picker_out = st_folium(
        picker_map,
        width="100%",
        height=260,
        key="report_picker_map",
        returned_objects=["last_clicked"],
    )

    if picker_out and picker_out.get("last_clicked"):
        clicked_coord = picker_out["last_clicked"]
        if (
            clicked_coord.get("lat")
            and (clicked_coord["lat"] != st.session_state["report_lat"] or clicked_coord["lng"] != st.session_state["report_lon"])
        ):
            st.session_state["report_lat"] = clicked_coord["lat"]
            st.session_state["report_lon"] = clicked_coord["lng"]
            st.rerun()

    # Landmark Proximity & Multiplier Feedback
    loc_type = get_location_type(lat_val, lon_val)
    multiplier_val = 1.5 if loc_type in ["school", "hospital"] else (1.3 if loc_type == "highway" else 1.0)
    st.markdown(
        f"""
        <div style="background:#FAFBFD;border:1px solid {TOKENS['border']};border-radius:6px;padding:6px 12px;font-size:12px;margin:8px 0;display:flex;justify-content:space-between;align-items:center">
          <span>Proximity Category: <strong>{loc_type.upper()}</strong></span>
          <span>Priority Multiplier: <strong style="color:{TOKENS['deep_teal']}">×{multiplier_val}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    from core.config import INDORE_AREAS  # noqa: PLC0415
    auto_area = reverse_geocode_area(lat_val, lon_val)
    area = st.selectbox(
        "Area / Neighbourhood",
        options=["Auto-detected (" + auto_area + ")"] + INDORE_AREAS,
        index=0,
    )
    final_area = auto_area if area.startswith("Auto-detected") else area

    # ── Submit ────────────────────────────────────────────────────────────────
    st.markdown(f'<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)

    if st.button("Submit Report to Queue", key="submit_report_btn", type="primary"):
        if not validate_coordinates(lat_val, lon_val):
            st.error("Invalid coordinates. Please pick a location on the map.")
            return

        priority = compute_priority(score, loc_type, 1)

        # Check for duplicate
        dup_id = find_duplicate(primary.class_name, lat_val, lon_val)

        if dup_id:
            merge_into(dup_id, file_path_saved, eff_conf, user)
            st.success(
                f"Merged with existing Issue #{dup_id} "
                f"(same hazard within 10 m radius). Report counter updated."
            )
            log_audit(user["username"], user["role"], "merged", dup_id,
                      f"Upload merged into issue #{dup_id}")
        else:
            issue_data = {
                "type":           primary.class_name,
                "severity_score": score,
                "severity_label": label,
                "priority":       priority,
                "lat":            lat_val,
                "lon":            lon_val,
                "area":           final_area or "Indore",
                "location_type":  loc_type,
                "image_path":     file_path_saved,
                "confidence":     eff_conf,
                "report_count":   1,
                "status":         "reported",
                "ai_assessment":  json.dumps(assess_dict) if assess_dict else None,
                "ai_model":       f"Google {GEMINI_MODEL}" if assess_dict else None,
                "detector_source": result.detector_used,
            }
            try:
                iid = create_issue(user, issue_data)
                log_audit(user["username"], user["role"], "upload", iid,
                          f"Reported {primary.class_name} in {area or 'Unknown'} via {result.detector_used}")

                if label == "High":
                    try:
                        send_high_severity_alert(iid, primary.class_name, area or "Unknown", [])
                    except Exception:
                        pass

                st.success(f"Issue #{iid} successfully submitted to the repair queue!")
                st.markdown(
                    f'<div style="font-size:13px;color:{TOKENS["muted"]};margin-top:0.5rem">'
                    f'Severity: {severity_badge(label)} &nbsp; Priority score: '
                    f'<strong>{priority:.3f}</strong> &nbsp; Location type: '
                    f'<strong>{loc_type}</strong></div>',
                    unsafe_allow_html=True,
                )
                # Clear state
                for k in ["report_result", "report_file_path", "report_is_video", "report_detector_used"]:
                    st.session_state.pop(k, None)
            except PermissionError as e:
                st.error(str(e))
