"""
CSS injection and color tokens for UrbanLens.
Call inject_css() once in app.py.
"""

from __future__ import annotations

import streamlit as st

# ─── Token map ────────────────────────────────────────────────────────────────
TOKENS = {
    "navy":          "#0B2545",
    "teal_deep":     "#136F63",
    "teal":          "#1B9C85",
    "mint":          "#6CC48A",
    "bg":            "#F5F7FA",
    "surface":       "#FFFFFF",
    "border":        "#E3E8EF",
    "muted":         "#5B6B7F",
    "high":          "#C8372D",
    "medium":        "#E08A1E",
    "low":           "#2E9E6B",
    "reported":      "#5B6B7F",
    "assigned":      "#2F6FB5",
    "fixed":         "#1B9C85",
    "text_primary":  "#0B2545",
}


def inject_css(hide_sidebar: bool = False) -> None:
    """Inject global custom CSS into the Streamlit app."""
    sidebar_hide_rule = ""
    if hide_sidebar:
        sidebar_hide_rule = """
        section[data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }
        """

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ── Reset & Typography ── */
        body, p, label, input, select, textarea,
        h1, h2, h3, h4, h5, h6,
        .stMarkdown, .stText, .stDataFrame, .stTable {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        }}
        body {{
            font-size: 16px !important;
            color: {TOKENS['navy']} !important;
        }}

        /* ── Protect Streamlit Material Symbols Icon Font ── */
        [data-testid="stIconMaterial"],
        [class*="material-symbols"],
        [class*="material-icons"],
        .material-icons,
        .material-symbols-rounded {{
            font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
            font-weight: normal !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
        }}

        /* ── Chrome Hiding (Keep sidebar collapse arrow functional) ── */
        #MainMenu {{ display: none !important; }}
        footer {{ display: none !important; }}
        .stDeployButton {{ display: none !important; }}
        div[data-testid="stDecoration"] {{ display: none !important; }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
            height: 2.2rem !important;
        }}
        header[data-testid="stHeader"] .stToolbarActions,
        header[data-testid="stHeader"] .stStatusWidget,
        header[data-testid="stHeader"] [data-testid="stToolbar"] {{
            display: none !important;
        }}
        /* Keep sidebar toggle button visible and styled cleanly */
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="baseButton-header"],
        [data-testid="stSidebarCollapsedControl"] button {{
            color: {TOKENS['navy']} !important;
            background: rgba(255, 255, 255, 0.9) !important;
            border: 1px solid {TOKENS['border']} !important;
            border-radius: 6px !important;
            visibility: visible !important;
        }}

        {sidebar_hide_rule}

        /* ── App background & layout ── */
        .stApp {{
            background: {TOKENS['bg']} !important;
        }}
        .main .block-container {{
            padding-top: 1.25rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1400px !important;
        }}

        /* ── Sidebar Styling ── */
        section[data-testid="stSidebar"] {{
            background: {TOKENS['navy']} !important;
            border-right: 1px solid #081a30 !important;
            width: 280px !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: #d6e4f7;
        }}
        section[data-testid="stSidebar"] a {{
            color: #9ac4e8 !important;
        }}

        /* Sidebar Sign Out Button (Outlined on Navy) */
        .sidebar-signout-btn > button {{
            background: transparent !important;
            color: #ffffff !important;
            border: 1.5px solid rgba(255, 255, 255, 0.35) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            padding: 0.5rem 1rem !important;
            width: 100% !important;
            transition: all 0.2s ease !important;
        }}
        .sidebar-signout-btn > button:hover {{
            background: rgba(255, 255, 255, 0.12) !important;
            border-color: #ffffff !important;
            color: #ffffff !important;
        }}

        /* Navigation items in sidebar */
        .sidebar-nav-btn button {{
            background: transparent !important;
            border: none !important;
            border-left: 3px solid transparent !important;
            border-radius: 0 6px 6px 0 !important;
            color: #d6e4f7 !important;
            font-size: 17px !important;
            font-weight: 500 !important;
            padding: 0.65rem 1rem !important;
            text-align: left !important;
            justify-content: flex-start !important;
            width: 100% !important;
            transition: all 0.15s ease-in-out !important;
        }}
        .sidebar-nav-btn button:hover {{
            background: rgba(255, 255, 255, 0.08) !important;
            color: #ffffff !important;
        }}
        .sidebar-nav-active button {{
            background: rgba(27, 156, 133, 0.22) !important;
            border-left: 3.5px solid {TOKENS['teal']} !important;
            color: #ffffff !important;
            font-weight: 600 !important;
        }}

        /* ── Button Hierarchy ── */
        .stButton > button {{
            font-family: 'Inter', sans-serif !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            padding: 0.55rem 1.25rem !important;
            transition: all 0.18s ease-in-out !important;
        }}
        /* Primary: Solid Deep Teal */
        .stButton > button[kind="primary"],
        .btn-primary > button,
        .btn-primary {{
            background: {TOKENS['teal_deep']} !important;
            color: #ffffff !important;
            border: 1px solid {TOKENS['teal_deep']} !important;
            box-shadow: 0 1px 2px rgba(11,37,69,0.08) !important;
        }}
        .stButton > button[kind="primary"]:hover,
        .btn-primary > button:hover {{
            background: {TOKENS['teal']} !important;
            border-color: {TOKENS['teal']} !important;
            box-shadow: 0 3px 6px rgba(19,111,99,0.18) !important;
        }}
        /* Secondary: Clean Outlined */
        .stButton > button[kind="secondary"],
        .btn-secondary > button {{
            background: #ffffff !important;
            color: {TOKENS['teal_deep']} !important;
            border: 1.5px solid {TOKENS['teal_deep']} !important;
        }}
        .stButton > button[kind="secondary"]:hover,
        .btn-secondary > button:hover {{
            background: #edf7f5 !important;
            border-color: {TOKENS['teal']} !important;
            color: {TOKENS['teal']} !important;
        }}
        /* Destructive */
        .btn-danger > button {{
            background: #ffffff !important;
            color: {TOKENS['high']} !important;
            border: 1.5px solid {TOKENS['high']} !important;
        }}
        .btn-danger > button:hover {{
            background: #fdf0ef !important;
        }}

        /* ── Form Inputs ── */
        .stTextInput input, .stTextArea textarea,
        .stSelectbox select, div[data-baseweb="select"] {{
            border: 1px solid {TOKENS['border']} !important;
            border-radius: 8px !important;
            background: #ffffff !important;
            font-size: 15px !important;
            color: {TOKENS['navy']} !important;
            padding: 0.5rem 0.75rem !important;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus {{
            border-color: {TOKENS['teal_deep']} !important;
            box-shadow: 0 0 0 3px rgba(19, 111, 99, 0.12) !important;
            outline: none !important;
        }}
        label, .stLabel {{
            font-size: 13px !important;
            font-weight: 600 !important;
            color: {TOKENS['muted']} !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px !important;
        }}

        /* ── Cards & Surfaces ── */
        .urban-card {{
            background: {TOKENS['surface']};
            border: 1px solid {TOKENS['border']};
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(11,37,69,0.04);
            margin-bottom: 1rem;
        }}

        /* ── Tables & Dataframes ── */
        .stDataFrame thead th {{
            background: {TOKENS['bg']} !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: {TOKENS['muted']} !important;
            padding: 10px 12px !important;
        }}
        .stDataFrame tbody tr:hover td {{
            background: #edf3fb !important;
        }}
        .stDataFrame td {{
            font-size: 15px !important;
            color: {TOKENS['navy']} !important;
        }}

        /* ── Map Attribution Removal ── */
        .leaflet-control-attribution {{
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}

        /* ── Tabular numbers ── */
        .tabnum {{ font-variant-numeric: tabular-nums; }}

        /* ── Live indicator ── */
        @keyframes pulse-live {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50%       {{ opacity: 0.35; transform: scale(0.9); }}
        }}
        .live-dot {{
            display: inline-block;
            width: 9px; height: 9px;
            border-radius: 50%;
            background: #2E9E6B;
            animation: pulse-live 1.8s ease-in-out infinite;
            vertical-align: middle;
            margin-right: 6px;
        }}

        @media (prefers-reduced-motion: reduce) {{
            .live-dot, .hero-watermark, .fade-in-card {{
                animation: none !important;
                transition: none !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
