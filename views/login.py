"""
UrbanLens Login Page.
Split-screen design: Left navy branded banner with value points,
Right clean authentication card with demo credentials and guest access.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from core.auth import login, continue_as_guest
from ui.theme import TOKENS


def _get_b64_image(path_str: str) -> str:
    """Read image and return data URI for HTML injection."""
    p = Path(path_str)
    if not p.exists():
        return ""
    try:
        suffix = p.suffix.lower().replace(".", "")
        mime = "image/png" if suffix == "png" else ("image/jpeg" if suffix in ("jpg", "jpeg") else "image/svg+xml")
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def render(on_back_to_landing=None) -> None:
    """Render the split-screen authentication portal."""
    logo_white_uri = _get_b64_image("assets/logo_white.png") or _get_b64_image("assets/logo_transparent.png")
    logo_trans_uri = _get_b64_image("assets/logo_transparent.png") or _get_b64_image("assets/icon.png")

    # CSS for Split-Screen Layout
    st.markdown(
        f"""
        <style>
        .split-login-container {{
            max-width: 1050px;
            margin: 1.5rem auto;
            background: #FFFFFF;
            border: 1px solid {TOKENS['border']};
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 12px 36px rgba(11,37,69,0.08);
        }}
        .login-left-pane {{
            background: linear-gradient(145deg, #0B2545 0%, #061527 100%);
            padding: 44px 36px;
            color: #FFFFFF;
            height: 100%;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .login-watermark {{
            position: absolute;
            right: -20px;
            bottom: -20px;
            width: 70%;
            opacity: 0.08;
            pointer-events: none;
            user-select: none;
            transform: rotate(-10deg);
        }}
        .login-right-pane {{
            padding: 40px 44px;
            background: #FFFFFF;
            height: 100%;
        }}
        .value-point {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 18px;
        }}
        .value-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: {TOKENS['teal']};
            margin-top: 6px;
            flex-shrink: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Top return link
    col_back, _ = st.columns([2, 8])
    with col_back:
        if st.button("← Back to Landing Page", key="login_back_btn"):
            if on_back_to_landing:
                on_back_to_landing()
            else:
                st.session_state["auth_view"] = "landing"
                st.rerun()

    st.markdown('<div style="margin-bottom:1rem"></div>', unsafe_allow_html=True)

    # Split columns
    left_col, right_col = st.columns([5, 6], gap="medium")

    with left_col:
        watermark_img = f'<img src="{logo_white_uri}" class="login-watermark"/>' if logo_white_uri else ''
        logo_header_img = f'<img src="{logo_white_uri}" style="height:36px;object-fit:contain;margin-bottom:12px"/>' if logo_white_uri else ''
        st.markdown(
            f"""
            <div class="login-left-pane" style="border-radius:12px">
              {watermark_img}
              <div>
                {logo_header_img}
                <div style="font-size:24px;font-weight:800;letter-spacing:-0.02em;margin-bottom:8px">
                  Urban<span style="color:{TOKENS['teal']}">Lens</span>
                </div>
                <div style="font-size:15px;color:#C2D5ED;margin-bottom:28px;line-height:1.4">
                  Seeing what the city needs fixed.
                </div>
                <div class="value-point">
                  <div class="value-dot"></div>
                  <div style="font-size:13px;color:#E8F0FB;line-height:1.4">
                    <strong>Hybrid AI Detection:</strong> YOLOv8 bounding boxes combined with Google Gemini qualitative safety assessments.
                  </div>
                </div>
                <div class="value-point">
                  <div class="value-dot"></div>
                  <div style="font-size:13px;color:#E8F0FB;line-height:1.4">
                    <strong>Objective Prioritization:</strong> Transparent multi-factor algorithmic scoring that balances severity and school/hospital proximity.
                  </div>
                </div>
                <div class="value-point">
                  <div class="value-dot"></div>
                  <div style="font-size:13px;color:#E8F0FB;line-height:1.4">
                    <strong>Role-Based Accountability:</strong> Full audit trail tracking every triage decision and status transition.
                  </div>
                </div>
              </div>
              <div style="font-size:12px;color:#9AC4E8;padding-top:20px;border-top:1px solid rgba(255,255,255,0.12)">
                Municipal Operations Platform · v1.4
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        st.markdown(
            f"""
            <div style="margin-bottom:1.5rem">
              <h2 style="font-size:24px;font-weight:700;color:{TOKENS['navy']};margin:0 0 6px 0">
                Sign in to UrbanLens
              </h2>
              <p style="font-size:14px;color:{TOKENS['muted']};margin:0">
                Enter your credentials or test with one-click demo accounts.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", value=st.session_state.get("fill_user", ""), placeholder="admin, officer1, or citizen1")
            password = st.text_input("Password", value=st.session_state.get("fill_pass", ""), type="password", placeholder="Enter your password")
            submit_btn = st.form_submit_button("Sign in", type="primary", use_container_width=True)

            if submit_btn:
                if not username or not password:
                    st.error("Please enter both username and password.")
                else:
                    with st.spinner("Authenticating…"):
                        ok, msg = login(username, password)
                        if ok:
                            st.session_state.pop("fill_user", None)
                            st.session_state.pop("fill_pass", None)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown(
            f"""
            <div style="display:flex;align-items:center;margin:1.25rem 0;color:{TOKENS['muted']};font-size:12px">
              <div style="flex:1;height:1px;background:{TOKENS['border']}"></div>
              <div style="padding:0 12px;font-weight:600;text-transform:uppercase">OR</div>
              <div style="flex:1;height:1px;background:{TOKENS['border']}"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Secondary action: Continue as Guest
        if st.button("Continue as Guest (Public Explorer)", key="guest_action_btn", use_container_width=True):
            continue_as_guest()
            st.rerun()

        # Demo Account Chips
        st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:12px;font-weight:700;color:{TOKENS["muted"]};text-transform:uppercase;letter-spacing:0.04em;margin-bottom:8px">'
            f'Demo Accounts (Click to Fill)</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        demo_accounts = [
            ("Admin",    "admin",    "admin123"),
            ("Officer",  "officer1", "officer123"),
            ("Citizen",  "citizen1", "citizen123"),
        ]
        for col, (label, user, pwd) in zip([c1, c2, c3], demo_accounts):
            with col:
                if st.button(f"{label}", key=f"chip_btn_{user}", use_container_width=True):
                    st.session_state["fill_user"] = user
                    st.session_state["fill_pass"] = pwd
                    st.rerun()
