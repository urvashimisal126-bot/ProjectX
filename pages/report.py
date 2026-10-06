"""Report an Issue page."""
from __future__ import annotations

import os
import io
import uuid
from pathlib import Path

import streamlit as st
from PIL import Image

from core.auth import current_user, require_role
from core.config import DEFAULT_LAT, DEFAULT_LON, ISSUE_CLASSES, ISSUE_LABELS, UPLOAD_DIR, DEFAULT_CONF_THRESHOLD
from core.detect import detect_image, detect_video, DEMO_MODE
from core.geo import extract_gps, get_location_type
from core.score import compute_severity, compute_priority, severity_breakdown
from core.db import create_issue
from core.dedupe import find_duplicate, merge_into
from core.audit import log_audit
from core.notify import send_high_severity_alert
from ui.components import page_header, severity_badge
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

    page_header("Report Issue", "Upload a photo or video — AI will detect and classify the problem.")

    if DEMO_MODE:
        st.warning(
            "**Demo mode:** using simulated detection — no model file found at models/best.pt. "
            "Results are illustrative only.",
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
    with st.expander("Advanced settings", expanded=False):
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
    if st.button("Analyse", key="analyse_btn"):
        with st.spinner("Running AI detection…"):
            try:
                if is_video:
                    result = detect_video(file_path, conf_threshold, selected_classes or ISSUE_CLASSES)
                else:
                    result = detect_image(file_path, conf_threshold, selected_classes or ISSUE_CLASSES)
            except Exception as e:
                st.error(f"Detection failed: {e}")
                return

        st.session_state["report_result"] = result
        st.session_state["report_file_path"] = file_path
        st.session_state["report_is_video"] = is_video

    result = st.session_state.get("report_result")
    file_path_saved = st.session_state.get("report_file_path", file_path)

    if result is None:
        return

    with col_analysis:
        st.markdown(f'<div style="font-size:13px;font-weight:700;color:{TOKENS["muted"]};margin-bottom:0.5rem">DETECTION RESULT</div>', unsafe_allow_html=True)
        st.image(result.annotated_image, use_container_width=True)

    if not result.detections:
        st.info("No infrastructure issues detected in this file. Try adjusting the confidence threshold.")
        return

    # ── Detection breakdown ───────────────────────────────────────────────────
    st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1rem 0 0.5rem">Detections</div>', unsafe_allow_html=True)

    # Use the highest-confidence detection as primary
    primary = max(result.detections, key=lambda d: d.confidence)
    detect_count = len(result.detections)

    score, label = compute_severity(primary.area_ratio, primary.confidence, detect_count)
    breakdown = severity_breakdown(
        primary.area_ratio, primary.confidence, detect_count, "default", 1
    )

    dcols = st.columns(len(result.detections))
    for i, det in enumerate(result.detections):
        with dcols[i]:
            s, l = compute_severity(det.area_ratio, det.confidence, detect_count)
            st.markdown(
                f'<div style="background:#fff;border:1px solid {TOKENS["border"]};'
                f'border-radius:8px;padding:0.75rem">'
                f'<div style="font-size:12px;font-weight:700;color:{TOKENS["muted"]};'
                f'text-transform:uppercase">{ISSUE_LABELS.get(det.class_name, det.class_name)}</div>'
                f'<div style="font-size:20px;font-weight:700;color:{TOKENS["navy"]};margin:4px 0">'
                f'{det.confidence:.0%}</div>'
                f'<div style="font-size:12px;color:{TOKENS["muted"]}">Confidence</div>'
                f'<div style="margin-top:8px">{severity_badge(l)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Location ──────────────────────────────────────────────────────────────
    st.markdown(f'<div style="font-size:14px;font-weight:700;color:{TOKENS["navy"]};margin:1.25rem 0 0.5rem">Location</div>', unsafe_allow_html=True)

    gps = extract_gps(file_path_saved) if not st.session_state.get("report_is_video") else None

    if gps:
        lat_val, lon_val = gps
        st.success(f"GPS extracted from image: {lat_val:.5f}, {lon_val:.5f}")
    else:
        st.info("No GPS data found. Please enter coordinates manually or use the defaults (Indore).")
        c_lat, c_lon = st.columns(2)
        with c_lat:
            lat_val = st.number_input("Latitude", value=DEFAULT_LAT, format="%.5f", key="lat_input")
        with c_lon:
            lon_val = st.number_input("Longitude", value=DEFAULT_LON, format="%.5f", key="lon_input")

    from core.config import INDORE_AREAS  # noqa: PLC0415
    area = st.selectbox("Area / Neighbourhood", options=[""] + INDORE_AREAS, index=0)

    # ── Submit ────────────────────────────────────────────────────────────────
    st.markdown(f'<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)

    if st.button("Submit Report", key="submit_report_btn"):
        loc_type = get_location_type(lat_val, lon_val)
        priority = compute_priority(score, loc_type, 1)

        # Check for duplicate
        dup_id = find_duplicate(primary.class_name, lat_val, lon_val)

        if dup_id:
            merge_into(dup_id, file_path_saved, primary.confidence, user)
            st.success(
                f"This issue was merged with existing Report #{dup_id} "
                f"(same type detected within 10 m). Report count updated."
            )
            log_audit(user["username"], user["role"], "merged", dup_id,
                      f"New upload merged into #{dup_id}")
        else:
            issue_data = {
                "type":           primary.class_name,
                "severity_score": score,
                "severity_label": label,
                "priority":       priority,
                "lat":            lat_val,
                "lon":            lon_val,
                "area":           area or "Unknown",
                "location_type":  loc_type,
                "image_path":     file_path_saved,
                "confidence":     primary.confidence,
                "report_count":   1,
                "status":         "reported",
            }
            try:
                iid = create_issue(user, issue_data)
                log_audit(user["username"], user["role"], "upload", iid,
                          f"Reported {primary.class_name} in {area or 'Unknown'}")

                if label == "High":
                    try:
                        send_high_severity_alert(iid, primary.class_name, area or "Unknown", [])
                    except Exception:
                        pass

                st.success(f"Issue #{iid} reported successfully!")
                st.markdown(
                    f'<div style="font-size:13px;color:{TOKENS["muted"]};margin-top:0.5rem">'
                    f'Severity: {severity_badge(label)} &nbsp; Priority score: '
                    f'<strong>{priority:.3f}</strong> &nbsp; Location type: '
                    f'<strong>{loc_type}</strong></div>',
                    unsafe_allow_html=True,
                )
                # Clear state
                for k in ["report_result", "report_file_path", "report_is_video"]:
                    st.session_state.pop(k, None)
            except PermissionError as e:
                st.error(str(e))
