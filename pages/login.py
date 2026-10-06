"""Login page."""
from __future__ import annotations
from pathlib import Path
import streamlit as st
from core.auth import login, continue_as_guest
from ui.theme import TOKENS


def render() -> None:
    # Center content
    _, col, _ = st.columns([1, 2, 1])
    with col:
        # Logo
        logo_path = Path("assets/logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=220)
        else:
            st.markdown(
                f'<div style="text-align:center;font-size:40px;font-weight:800;'
                f'color:{TOKENS["navy"]};margin-bottom:0.5rem">'
                f'Urban<span style="color:{TOKENS["teal"]}">Lens</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<p style="text-align:center;color:{TOKENS["muted"]};'
            f'font-size:14px;margin-top:-4px;margin-bottom:1.5rem">'
            f'Seeing what the city needs fixed.</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="background:#fff;border:1px solid {TOKENS["border"]};'
            f'border-radius:12px;padding:1.75rem 2rem">',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<h2 style="font-size:18px;font-weight:700;color:{TOKENS["navy"]};'
            f'margin:0 0 1.25rem 0">Sign in to UrbanLens</h2>',
            unsafe_allow_html=True,
        )

        username = st.text_input("Username", placeholder="Enter your username", key="login_user")
        password = st.text_input("Password", placeholder="Enter your password", type="password", key="login_pass")

        if st.button("Sign in", use_container_width=True, key="login_btn"):
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                ok, msg = login(username, password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown('<div style="margin:1rem 0;border-top:1px solid #E3E8EF"></div>', unsafe_allow_html=True)
        if st.button("Continue as Guest", use_container_width=True, key="guest_btn"):
            continue_as_guest()
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Demo account chips
        st.markdown('<div style="margin-top:1rem">', unsafe_allow_html=True)
        st.markdown(
            f'<p style="font-size:12px;color:{TOKENS["muted"]};text-align:center;margin-bottom:6px">'
            f'Demo accounts — click to fill</p>',
            unsafe_allow_html=True,
        )
        chip_cols = st.columns(4)
        demo_accounts = [
            ("Admin",    "admin",    "admin123"),
            ("Officer",  "officer1", "officer123"),
            ("Citizen",  "citizen1", "citizen123"),
        ]
        for i, (label, user, pwd) in enumerate(demo_accounts):
            with chip_cols[i]:
                if st.button(label, key=f"chip_{user}", use_container_width=True):
                    st.session_state["login_user"] = user
                    st.session_state["login_pass"] = pwd
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
