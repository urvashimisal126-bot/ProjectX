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


def inject_css() -> None:
    """Inject all custom CSS into the Streamlit app."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* ── Reset & base ── */
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif !important;
            color: {TOKENS['navy']};
        }}

        /* Hide Streamlit chrome */
        #MainMenu, footer, .stDeployButton,
        header[data-testid="stHeader"] {{ display: none !important; }}

        /* ── App background ── */
        .stApp {{
            background: {TOKENS['bg']} !important;
        }}

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] {{
            background: {TOKENS['navy']} !important;
            border-right: 1px solid #0a1e38;
        }}
        section[data-testid="stSidebar"] * {{
            color: #d6e4f7 !important;
        }}
        section[data-testid="stSidebar"] a {{
            color: #9ac4e8 !important;
        }}
        section[data-testid="stSidebar"] .stButton > button {{
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            color: #d6e4f7 !important;
            width: 100%;
            text-align: left;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(255,255,255,0.08) !important;
        }}

        /* ── Primary button ── */
        .stButton > button[kind="primary"],
        .stButton > button {{
            background: {TOKENS['teal_deep']} !important;
            color: #fff !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            padding: 0.45rem 1.1rem !important;
            transition: background 0.15s;
        }}
        .stButton > button:hover {{
            background: {TOKENS['teal']} !important;
        }}
        /* Secondary buttons via container class */
        .btn-secondary > button {{
            background: #fff !important;
            color: {TOKENS['teal_deep']} !important;
            border: 1.5px solid {TOKENS['teal_deep']} !important;
        }}
        .btn-secondary > button:hover {{
            background: #edf7f5 !important;
        }}
        /* Destructive */
        .btn-danger > button {{
            background: #fff !important;
            color: {TOKENS['high']} !important;
            border: 1.5px solid {TOKENS['high']} !important;
        }}

        /* ── Inputs ── */
        .stTextInput input, .stTextArea textarea,
        .stSelectbox select, div[data-baseweb="select"] {{
            border: 1px solid {TOKENS['border']} !important;
            border-radius: 6px !important;
            background: #fff !important;
            font-size: 14px !important;
            color: {TOKENS['navy']} !important;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus {{
            border-color: {TOKENS['teal_deep']} !important;
            box-shadow: 0 0 0 3px rgba(19,111,99,0.12) !important;
            outline: none !important;
        }}
        label, .stLabel {{
            font-size: 13px !important;
            font-weight: 600 !important;
            color: {TOKENS['muted']} !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
            border-bottom: 2px solid {TOKENS['border']};
            background: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-size: 13px !important;
            font-weight: 600 !important;
            color: {TOKENS['muted']} !important;
            padding: 0.5rem 1rem !important;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            background: transparent !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: {TOKENS['teal_deep']} !important;
            border-bottom: 2px solid {TOKENS['teal_deep']} !important;
        }}

        /* ── Dataframe / table ── */
        .stDataFrame thead th {{
            background: {TOKENS['bg']} !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {TOKENS['muted']} !important;
        }}
        .stDataFrame tbody tr:hover td {{
            background: #edf3fb !important;
        }}

        /* ── Expander ── */
        .stExpander {{
            border: 1px solid {TOKENS['border']} !important;
            border-radius: 8px !important;
        }}
        .stExpander summary {{
            font-size: 13px !important;
            font-weight: 600 !important;
        }}

        /* ── Metric ── */
        div[data-testid="metric-container"] {{
            background: #fff;
            border: 1px solid {TOKENS['border']};
            border-radius: 10px;
            padding: 1rem 1.2rem;
        }}

        /* ── Alerts / status messages ── */
        div[data-testid="stAlert"] {{
            border-radius: 8px !important;
            font-size: 14px !important;
        }}

        /* ── Slider ── */
        .stSlider [data-testid="stSlider"] {{
            accent-color: {TOKENS['teal_deep']};
        }}

        /* ── File uploader ── */
        section[data-testid="stFileUploadDropzone"] {{
            border: 2px dashed {TOKENS['border']} !important;
            border-radius: 10px !important;
            background: {TOKENS['bg']} !important;
        }}

        /* ── Progress bar ── */
        .stProgress > div > div {{
            background: {TOKENS['teal_deep']} !important;
        }}

        /* ── Spinner ── */
        .stSpinner > div {{
            border-top-color: {TOKENS['teal_deep']} !important;
        }}

        /* ── Tabular numbers ── */
        .tabnum {{ font-variant-numeric: tabular-nums; }}

        /* ── Live indicator ── */
        @keyframes pulse-live {{
            0%, 100% {{ opacity: 1; }}
            50%       {{ opacity: 0.3; }}
        }}
        .live-dot {{
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #2E9E6B;
            animation: pulse-live 1.8s ease-in-out infinite;
            vertical-align: middle;
            margin-right: 5px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
