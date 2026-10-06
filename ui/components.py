"""
Reusable UI components for UrbanLens.
Designed for high aesthetic quality, clarity, and robust safety net handling.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from ui.theme import TOKENS


# ─── Relative time ────────────────────────────────────────────────────────────

def relative_time(ts_str: str) -> str:
    """Convert a UTC timestamp string to '2h ago' style."""
    try:
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ts_str or "—"


# ─── Badges (Pills) ───────────────────────────────────────────────────────────

_SEV_COLORS = {
    "High":   (TOKENS["high"],    "#fdf0ef", "#f8d7da"),
    "Medium": (TOKENS["medium"],  "#fdf6ec", "#ffeeba"),
    "Low":    (TOKENS["low"],     "#edf8f2", "#c3e6cb"),
}
_STATUS_COLORS = {
    "reported": (TOKENS["reported"], "#f2f4f7", "#d6d8db"),
    "assigned": (TOKENS["assigned"], "#edf3fb", "#b8daff"),
    "fixed":    (TOKENS["fixed"],    "#edf8f5", "#c3e6cb"),
}


def severity_badge(label: str) -> str:
    """Return an accessible, pill-style HTML badge for severity level."""
    color, bg, border = _SEV_COLORS.get(label, (TOKENS["muted"], "#f2f4f7", "#e3e8ef"))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {border};'
        f'border-radius:9999px;padding:3px 10px;font-size:12px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.04em;display:inline-block">'
        f'{label}</span>'
    )


def status_badge(status: str) -> str:
    """Return an accessible, pill-style HTML badge for issue status."""
    color, bg, border = _STATUS_COLORS.get(status.lower(), (TOKENS["muted"], "#f2f4f7", "#e3e8ef"))
    label = status.capitalize()
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {border};'
        f'border-radius:9999px;padding:3px 10px;font-size:12px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.04em;display:inline-block">'
        f'{label}</span>'
    )


# ─── Page Header ──────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str, live: bool = False) -> None:
    """Render a standardized page title banner with optional live sync indicator."""
    live_html = ""
    if live:
        ts = datetime.now().strftime("%H:%M:%S")
        live_html = (
            f'<div style="float:right;display:flex;align-items:center;padding-top:6px">'
            f'<span class="live-dot"></span>'
            f'<span style="font-size:13px;color:{TOKENS["muted"]};font-weight:600">LIVE · {ts}</span>'
            f'</div>'
        )
    st.markdown(
        f"""
        <div style="border-bottom:1px solid {TOKENS['border']};
                    padding-bottom:1rem;margin-bottom:1.5rem">
          {live_html}
          <h1 style="font-size:32px;font-weight:700;margin:0 0 6px 0;
                     color:{TOKENS['navy']};letter-spacing:-0.02em">{title}</h1>
          <p style="font-size:15px;color:{TOKENS['muted']};margin:0;line-height:1.4">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── KPI Card ─────────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = "", delta_good: bool = True, hint: str = "") -> None:
    """
    Render an equal-height KPI metric card with 40px tabular numerals,
    aligned baselines, and consistent 24px padding.
    """
    delta_html = ""
    if delta:
        delta_color = TOKENS["low"] if delta_good else TOKENS["high"]
        delta_bg = "#edf8f2" if delta_good else "#fdf0ef"
        delta_html = (
            f'<span style="display:inline-block;margin-top:6px;font-size:12px;'
            f'font-weight:600;color:{delta_color};background:{delta_bg};'
            f'padding:2px 8px;border-radius:4px">{delta}</span>'
        )
    elif hint:
        delta_html = f'<div style="margin-top:6px;font-size:12px;color:{TOKENS["muted"]}">{hint}</div>'

    st.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid {TOKENS['border']};
                    border-radius:12px;padding:24px;min-height:140px;
                    display:flex;flex-direction:column;justify-content:space-between;
                    box-shadow:0 1px 3px rgba(11,37,69,0.04)">
          <div style="font-size:12px;font-weight:700;color:{TOKENS['muted']};
                      text-transform:uppercase;letter-spacing:0.06em">
            {label}
          </div>
          <div style="font-size:40px;font-weight:700;color:{TOKENS['navy']};
                      font-variant-numeric:tabular-nums;line-height:1.1;margin:8px 0 4px 0">
            {value}
          </div>
          {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Status Timeline (Stepper) ────────────────────────────────────────────────

def status_timeline(audit_rows: list[dict]) -> None:
    """Render a clean civic operations status stepper."""
    STATUS_ORDER = ["reported", "assigned", "fixed"]
    state: dict[str, dict] = {}
    for row in audit_rows:
        action = row.get("action", "")
        if action in STATUS_ORDER or action in ("upload", "merged"):
            key = "reported" if action in ("upload", "reported") else action
            state.setdefault(key, row)

    steps = [
        ("reported", "Reported",  "Issue logged with visual proof and coordinates"),
        ("assigned", "Assigned",  "Dispatched to municipal maintenance crew"),
        ("fixed",    "Fixed",     "Repairs verified and issue resolved"),
    ]
    html_parts = ['<div style="position:relative;padding-left:36px;margin:1rem 0">']
    for i, (key, label, hint) in enumerate(steps):
        row = state.get(key)
        if row:
            dot_color = TOKENS["teal_deep"]
            detail = f'{row.get("user", "System")} · {relative_time(row.get("timestamp", ""))}'
            opacity = "1"
        else:
            dot_color = TOKENS["border"]
            detail = "Pending action"
            opacity = "0.55"

        connector = ""
        if i < len(steps) - 1:
            connector = (
                f'<div style="position:absolute;left:13px;top:30px;'
                f'width:2px;height:38px;background:{TOKENS["border"]}"></div>'
            )
        html_parts.append(
            f"""
            <div style="position:relative;margin-bottom:28px;opacity:{opacity}">
              <div style="position:absolute;left:-36px;top:2px;
                          width:24px;height:24px;border-radius:50%;
                          background:{dot_color};border:3px solid #fff;
                          box-shadow:0 0 0 2px {dot_color}"></div>
              {connector}
              <div style="font-size:15px;font-weight:700;color:{TOKENS['navy']}">{label}</div>
              <div style="font-size:13px;color:{TOKENS['muted']};margin-top:2px">{hint}</div>
              <div style="font-size:12px;color:{TOKENS['teal_deep']};margin-top:2px;font-weight:600">{detail}</div>
            </div>
            """
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ─── Empty State ──────────────────────────────────────────────────────────────

def empty_state(title: str, body: str, action_label: str = "", action_key: str = "") -> bool:
    """Render a clean empty state card."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:3.5rem 1.5rem;background:#FFFFFF;
                    border:1px dashed {TOKENS['border']};border-radius:12px;margin:1rem 0">
          <div style="width:48px;height:48px;margin:0 auto 16px auto;border-radius:50%;
                      background:#F5F7FA;display:flex;align-items:center;justify-content:center;
                      color:{TOKENS['muted']};font-size:20px;font-weight:bold">
            0
          </div>
          <div style="font-size:18px;font-weight:700;color:{TOKENS['navy']};margin-bottom:6px">
            {title}
          </div>
          <div style="font-size:14px;color:{TOKENS['muted']};max-width:420px;margin:0 auto 16px auto">
            {body}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_label and action_key:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            return st.button(action_label, key=action_key, use_container_width=True)
    return False


# ─── Friendly Error Card (Safety Net) ─────────────────────────────────────────

def friendly_error_card(title: str, message: str, exc: Exception | None = None) -> None:
    """
    Safety net error card displayed when a view encounters an unexpected error.
    Prevents blank pages and allows expanding technical traceback.
    """
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else ""
    st.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid #f8d7da;border-left:4px solid {TOKENS['high']};
                    border-radius:10px;padding:20px;margin:1.5rem 0;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
          <div style="font-size:17px;font-weight:700;color:{TOKENS['high']};margin-bottom:6px">
            {title}
          </div>
          <div style="font-size:14px;color:{TOKENS['navy']};line-height:1.5">
            {message}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if tb_str:
        with st.expander("Technical details & error log"):
            st.code(tb_str, language="python")
            st.caption("You can report this issue or refresh the view.")


# ─── Sidebar User Card ────────────────────────────────────────────────────────

def sidebar_user_card(user: dict) -> None:
    """Render a clean user profile card at the bottom of the navy sidebar."""
    role_colors = {
        "admin":   ("#FFF3CD", "#856404"),
        "officer": ("#D1ECF1", "#0C5460"),
        "citizen": ("#D4EDDA", "#155724"),
        "guest":   ("#E2E3E5", "#383D41"),
    }
    bg, fg = role_colors.get(user.get("role", "guest"), ("#E2E3E5", "#383D41"))
    role_label = user.get("role", "guest").upper()
    name = user.get("name", "Public User")
    username = user.get("username", "guest")

    st.sidebar.markdown(
        f"""
        <div style="border-top:1px solid rgba(255,255,255,0.12);
                    padding-top:1rem;margin-top:1.5rem">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <div style="font-size:14px;font-weight:700;color:#FFFFFF">{name}</div>
            <span style="background:{bg};color:{fg};border-radius:4px;
                         padding:2px 6px;font-size:10px;font-weight:700;
                         letter-spacing:0.04em">{role_label}</span>
          </div>
          <div style="font-size:12px;color:#9ac4e8">@{username}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── AI Assessment Card ───────────────────────────────────────────────────────

def ai_assessment_card(assessment: dict | None, model_name: str = "Google Gemini") -> None:
    """Render a structured AI inspection assessment card."""
    if not assessment:
        st.markdown(
            f"""
            <div style="background:{TOKENS['surface']};border:1px solid {TOKENS['border']};
                        border-radius:10px;padding:1.25rem;margin-top:1rem">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                <span style="font-size:14px;font-weight:700;color:{TOKENS['navy']}">
                  AI Qualitative Assessment
                </span>
                <span style="font-size:12px;color:{TOKENS['muted']}">Powered by Google Gemini</span>
              </div>
              <div style="font-size:14px;color:{TOKENS['muted']};line-height:1.5">
                AI qualitative assessment is currently in deterministic mode (Gemini key not configured or image unconfirmed).
                Automated multi-factor priority scoring remains active.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    confirmed = assessment.get("confirmed", True)
    hazard_type = assessment.get("hazard_type", "hazard").replace("_", " ").title()
    sev_hint = assessment.get("severity_hint", "medium").upper()
    risk = assessment.get("risk_to_public", "")
    desc = assessment.get("description", "")
    action = assessment.get("recommended_action", "")
    urgency = assessment.get("urgency_reason", "")
    agrees = assessment.get("agrees_with_yolo")

    sev_color = TOKENS["high"] if sev_hint == "HIGH" else (TOKENS["medium"] if sev_hint == "MEDIUM" else TOKENS["low"])
    conf_badge = '<span style="background:#edf8f2;color:#1B9C85;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">CONFIRMED</span>' if confirmed else '<span style="background:#fdf0ef;color:#C8372D;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">UNCONFIRMED</span>'

    agreement_html = ""
    if agrees is True:
        agreement_html = '<span style="background:#edf8f5;color:#136F63;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px">YOLO & Gemini Agree</span>'
    elif agrees is False:
        agreement_html = '<span style="background:#fdf6ec;color:#E08A1E;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px">Detector Disagreement</span>'

    st.markdown(
        f"""
        <div style="background:{TOKENS['surface']};border:1px solid {TOKENS['border']};
                    border-radius:10px;padding:1.25rem;margin-top:1rem;box-shadow:0 1px 3px rgba(11,37,69,0.04)">
          <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {TOKENS['border']};padding-bottom:0.75rem;margin-bottom:0.85rem">
            <div style="display:flex;align-items:center">
              <span style="font-size:14px;font-weight:700;color:{TOKENS['navy']}">
                AI Inspection Assessment
              </span>
              {agreement_html}
            </div>
            <div style="font-size:12px;color:{TOKENS['muted']}">
              {conf_badge} <span style="margin-left:6px;color:{TOKENS['teal_deep']};font-weight:600">{model_name}</span>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:0.85rem">
            <div>
              <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Hazard Assessment</div>
              <div style="font-size:14px;font-weight:600;color:{TOKENS['navy']}">{hazard_type} <span style="color:{sev_color};font-weight:700">({sev_hint})</span></div>
            </div>
            <div>
              <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Recommended Action</div>
              <div style="font-size:14px;font-weight:600;color:{TOKENS['navy']}">{action or 'Site inspection required'}</div>
            </div>
          </div>

          <div style="margin-bottom:0.75rem">
            <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Visual Condition</div>
            <div style="font-size:14px;color:{TOKENS['navy']};line-height:1.45">{desc}</div>
          </div>

          <div style="margin-bottom:0.75rem">
            <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Public Safety Impact</div>
            <div style="font-size:14px;color:{TOKENS['navy']};line-height:1.45">{risk}</div>
          </div>

          <div>
            <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Urgency Rationale</div>
            <div style="font-size:13px;color:{TOKENS['muted']};line-height:1.45">{urgency}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
