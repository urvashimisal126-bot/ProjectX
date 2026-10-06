"""
Reusable HTML/CSS components for UrbanLens UI.
"""

from __future__ import annotations

from datetime import datetime, timezone

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


# ─── Severity badge ───────────────────────────────────────────────────────────

_SEV_COLORS = {
    "High":   (TOKENS["high"],    "#fdf0ef"),
    "Medium": (TOKENS["medium"],  "#fdf6ec"),
    "Low":    (TOKENS["low"],     "#edf8f2"),
}
_STATUS_COLORS = {
    "reported": (TOKENS["reported"], "#f2f4f7"),
    "assigned": (TOKENS["assigned"], "#edf3fb"),
    "fixed":    (TOKENS["fixed"],    "#edf8f5"),
}


def severity_badge(label: str) -> str:
    color, bg = _SEV_COLORS.get(label, (TOKENS["muted"], "#f2f4f7"))
    return (
        f'<span style="background:{bg};color:{color};border-radius:4px;'
        f'padding:2px 8px;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.05em">{label}</span>'
    )


def status_badge(status: str) -> str:
    color, bg = _STATUS_COLORS.get(status.lower(), (TOKENS["muted"], "#f2f4f7"))
    label = status.capitalize()
    return (
        f'<span style="background:{bg};color:{color};border-radius:4px;'
        f'padding:2px 8px;font-size:11px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.05em">{label}</span>'
    )


# ─── Page header ─────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str, live: bool = False) -> None:
    live_html = ""
    if live:
        from datetime import datetime as _dt  # noqa: PLC0415
        ts = _dt.now().strftime("%H:%M:%S")
        live_html = (
            f'<span style="float:right;font-size:12px;color:{TOKENS["muted"]};'
            f'font-weight:500;padding-top:4px">'
            f'<span class="live-dot"></span>Updated {ts}</span>'
        )
    st.markdown(
        f"""
        <div style="border-bottom:1px solid {TOKENS['border']};
                    padding-bottom:0.75rem;margin-bottom:1.25rem">
          {live_html}
          <h1 style="font-size:22px;font-weight:700;margin:0 0 4px 0;
                     color:{TOKENS['navy']}">{title}</h1>
          <p style="font-size:13px;color:{TOKENS['muted']};margin:0">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── KPI card ─────────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, delta: str = "", delta_good: bool = True, sparkline: list[int] | None = None) -> None:
    delta_color = TOKENS["low"] if delta_good else TOKENS["high"]
    delta_html = f'<span style="font-size:12px;color:{delta_color};font-weight:600">{delta}</span>' if delta else ""

    spark_html = ""
    if sparkline:
        max_v = max(sparkline) or 1
        bars = "".join(
            f'<span style="display:inline-block;width:4px;height:{int(h/max_v*24)+2}px;'
            f'background:{TOKENS["teal"]};border-radius:2px;margin-right:1px;'
            f'vertical-align:bottom"></span>'
            for h in sparkline[-14:]
        )
        spark_html = f'<div style="margin-top:8px">{bars}</div>'

    st.markdown(
        f"""
        <div style="background:#fff;border:1px solid {TOKENS['border']};
                    border-radius:10px;padding:1rem 1.2rem;height:100%">
          <div style="font-size:11px;font-weight:700;color:{TOKENS['muted']};
                      text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">
            {label}
          </div>
          <div style="font-size:28px;font-weight:700;color:{TOKENS['navy']};
                      font-variant-numeric:tabular-nums;line-height:1.1">
            {value}
          </div>
          {delta_html}
          {spark_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Status timeline stepper ──────────────────────────────────────────────────

def status_timeline(audit_rows: list[dict]) -> None:
    """Render an order-tracking style vertical stepper."""
    STATUS_ORDER = ["reported", "assigned", "fixed"]
    # Find the latest timestamp for each status action
    state: dict[str, dict] = {}
    for row in audit_rows:
        action = row.get("action", "")
        if action in STATUS_ORDER or action in ("upload", "merged"):
            key = "reported" if action in ("upload", "reported") else action
            state.setdefault(key, row)

    steps = [
        ("reported", "Reported",  "Issue submitted and logged"),
        ("assigned", "Assigned",  "Assigned to field officer"),
        ("fixed",    "Fixed",     "Issue resolved and closed"),
    ]
    html_parts = ['<div style="position:relative;padding-left:32px">']
    for i, (key, label, hint) in enumerate(steps):
        row = state.get(key)
        if row:
            dot_color = TOKENS["teal_deep"]
            detail = f'{row["user"]} · {relative_time(row["timestamp"])}'
            opacity = "1"
        else:
            dot_color = TOKENS["border"]
            detail = "Pending"
            opacity = "0.5"

        connector = ""
        if i < len(steps) - 1:
            connector = (
                f'<div style="position:absolute;left:11px;top:28px;'
                f'width:2px;height:32px;background:{TOKENS["border"]}"></div>'
            )
        html_parts.append(
            f"""
            <div style="position:relative;margin-bottom:24px;opacity:{opacity}">
              <div style="position:absolute;left:-32px;top:2px;
                          width:22px;height:22px;border-radius:50%;
                          background:{dot_color};border:3px solid #fff;
                          box-shadow:0 0 0 2px {dot_color}"></div>
              {connector}
              <div style="font-size:14px;font-weight:700;color:{TOKENS['navy']}">{label}</div>
              <div style="font-size:12px;color:{TOKENS['muted']};margin-top:2px">{hint}</div>
              <div style="font-size:12px;color:{TOKENS['teal_deep']};margin-top:2px;font-weight:600">{detail}</div>
            </div>
            """
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


# ─── Empty state ──────────────────────────────────────────────────────────────

def empty_state(title: str, body: str, icon: str = "●") -> None:
    st.markdown(
        f"""
        <div style="text-align:center;padding:3rem 1rem;color:{TOKENS['muted']}">
          <div style="font-size:36px;margin-bottom:12px;color:{TOKENS['border']}">{icon}</div>
          <div style="font-size:16px;font-weight:600;color:{TOKENS['navy']};
                      margin-bottom:6px">{title}</div>
          <div style="font-size:13px">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── Sidebar user block ───────────────────────────────────────────────────────

def sidebar_user_block(user: dict) -> None:
    role_colors = {
        "admin":   ("#FFF3CD", "#856404"),
        "officer": ("#D1ECF1", "#0C5460"),
        "citizen": ("#D4EDDA", "#155724"),
        "guest":   ("#E2E3E5", "#383D41"),
    }
    bg, fg = role_colors.get(user.get("role", "guest"), ("#E2E3E5", "#383D41"))
    role_label = user.get("role", "guest").capitalize()
    name = user.get("name", "Guest")
    st.sidebar.markdown(
        f"""
        <div style="border-top:1px solid rgba(255,255,255,0.1);
                    padding-top:1rem;margin-top:1rem">
          <div style="font-size:13px;font-weight:700;color:#e8f0fb">{name}</div>
          <span style="background:{bg};color:{fg};border-radius:4px;
                       padding:2px 8px;font-size:11px;font-weight:700;
                       text-transform:uppercase">{role_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─── AI Assessment Card ───────────────────────────────────────────────────────

def ai_assessment_card(assessment: dict | None, model_name: str = "Google Gemini") -> None:
    """Render a structured AI assessment card matching the civic operations theme."""
    if not assessment:
        st.markdown(
            f"""
            <div style="background:{TOKENS['surface']};border:1px solid {TOKENS['border']};
                        border-radius:8px;padding:1rem 1.25rem;margin-top:0.75rem">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
                <span style="font-size:13px;font-weight:700;color:{TOKENS['navy']};letter-spacing:0.02em">
                  AI Assessment
                </span>
                <span style="font-size:11px;color:{TOKENS['muted']}">Powered by Google Gemini</span>
              </div>
              <div style="font-size:13px;color:{TOKENS['muted']};line-height:1.5">
                AI qualitative assessment is currently unavailable (offline mode or API key unconfigured).
                Automated deterministic scoring remains fully active.
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
        agreement_html = '<span style="background:#edf8f5;color:#136F63;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px">YOLO & Gemini Agree</span>'
    elif agrees is False:
        agreement_html = '<span style="background:#fdf6ec;color:#E08A1E;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:600;margin-left:8px">Detector Disagreement</span>'

    st.markdown(
        f"""
        <div style="background:{TOKENS['surface']};border:1px solid {TOKENS['border']};
                    border-radius:8px;padding:1.2rem;margin-top:0.75rem;box-shadow:0 1px 3px rgba(0,0,0,0.03)">
          <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {TOKENS['border']};padding-bottom:0.6rem;margin-bottom:0.8rem">
            <div style="display:flex;align-items:center">
              <span style="font-size:13px;font-weight:700;color:{TOKENS['navy']};letter-spacing:0.02em">
                AI Inspection Assessment
              </span>
              {agreement_html}
            </div>
            <div style="font-size:11px;color:{TOKENS['muted']}">
              {conf_badge} <span style="margin-left:6px;color:{TOKENS['deep_teal']};font-weight:600">{model_name}</span>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-bottom:0.8rem">
            <div>
              <div style="font-size:11px;font-weight:600;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Hazard Assessment</div>
              <div style="font-size:13px;font-weight:600;color:{TOKENS['navy']}">{hazard_type} <span style="color:{sev_color};font-weight:700">({sev_hint})</span></div>
            </div>
            <div>
              <div style="font-size:11px;font-weight:600;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Recommended Action</div>
              <div style="font-size:13px;font-weight:600;color:{TOKENS['navy']}">{action or 'Site inspection'}</div>
            </div>
          </div>

          <div style="margin-bottom:0.6rem">
            <div style="font-size:11px;font-weight:600;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Visual Condition</div>
            <div style="font-size:13px;color:{TOKENS['navy']};line-height:1.4">{desc}</div>
          </div>

          <div style="margin-bottom:0.6rem">
            <div style="font-size:11px;font-weight:600;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Public Safety Impact</div>
            <div style="font-size:13px;color:{TOKENS['navy']};line-height:1.4">{risk}</div>
          </div>

          <div>
            <div style="font-size:11px;font-weight:600;color:{TOKENS['muted']};text-transform:uppercase;margin-bottom:2px">Urgency Rationale</div>
            <div style="font-size:12px;color:{TOKENS['muted']};line-height:1.4">{urgency}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

