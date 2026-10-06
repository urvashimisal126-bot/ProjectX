"""
Analytics page — Municipal infrastructure trend analysis, severity breakdowns,
resolution velocity, and AI-synthesized operations brief (Admin & Officer only).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.auth import current_user, require_role
from core.db import list_issues
from core.audit import log_audit
from core.config import ISSUE_CLASSES, ISSUE_LABELS
from ui.components import page_header, empty_state, friendly_error_card
from ui.theme import TOKENS


_PALETTE = [TOKENS["teal_deep"], TOKENS["teal"], TOKENS["mint"], TOKENS["navy"], TOKENS["medium"]]


def _chart_layout(fig, height: int = 300) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=24, b=10),
        font=dict(family="Inter", size=13, color=TOKENS["navy"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=TOKENS["border"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=TOKENS["border"], zeroline=False)
    return fig


def _card_header(title: str) -> None:
    st.markdown(
        f'<div style="font-size:15px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.6rem">{title}</div>',
        unsafe_allow_html=True,
    )


def render() -> None:
    require_role(["admin", "officer"])
    user = current_user()

    page_header(
        "Analytics",
        "Infrastructure incident trends, severity distributions, and municipal resolution velocity.",
    )

    issues = list_issues(user)
    if not issues:
        empty_state("No data recorded", "Submit issue reports to generate live operational analytics.")
        return

    try:
        df = pd.DataFrame(issues)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df = df.dropna(subset=["created_at"])
        df["date"] = df["created_at"].dt.date
    except Exception as exc:
        friendly_error_card("Data Processing Error", "Could not parse issues timestamps.", exc=exc)
        return

    # ── Top Filters ───────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    min_date = df["date"].min()
    max_date = df["date"].max()

    with fc1:
        date_range = st.date_input(
            "Date Range",
            value=[min_date, max_date],
            key="analytics_dates",
        )
    with fc2:
        f_type = st.multiselect(
            "Hazard Type",
            options=ISSUE_CLASSES,
            format_func=lambda x: ISSUE_LABELS.get(x, x),
            key="an_type",
        )
    with fc3:
        f_sev = st.multiselect("Severity", ["High", "Medium", "Low"], key="an_sev")

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        df = df[(df["date"] >= date_range[0]) & (df["date"] <= date_range[1])]
    if f_type:
        df = df[df["type"].isin(f_type)]
    if f_sev:
        df = df[df["severity_label"].isin(f_sev)]

    if df.empty:
        empty_state("No matching records", "No infrastructure reports match the selected filters.")
        return

    st.markdown('<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)

    # ── Row 1: Issues by Type | Severity Distribution ─────────────────────────
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        _card_header("Issues by Hazard Category")
        type_counts = df.groupby("type").size().reset_index(name="count")
        type_counts["label"] = type_counts["type"].map(lambda x: ISSUE_LABELS.get(x, x))
        fig = px.bar(
            type_counts, x="label", y="count", color="label",
            color_discrete_sequence=_PALETTE, text="count",
        )
        fig.update_traces(textposition="outside", marker_line_width=0)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total Count")
        st.plotly_chart(_chart_layout(fig), use_container_width=True, config={"displayModeBar": False})

    with col2:
        _card_header("Severity Distribution Split")
        sev_counts = df.groupby("severity_label").size().reset_index(name="count")
        sev_colors = {"High": TOKENS["high"], "Medium": TOKENS["medium"], "Low": TOKENS["low"]}
        fig2 = px.pie(
            sev_counts, names="severity_label", values="count",
            color="severity_label",
            color_discrete_map=sev_colors,
            hole=0.45,
        )
        fig2.update_traces(textinfo="label+percent", pull=[0.02] * len(sev_counts))
        fig2.update_layout(showlegend=False)
        st.plotly_chart(_chart_layout(fig2), use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

    # ── Row 2: Status Funnel | Resolved Over Time ─────────────────────────────
    col3, col4 = st.columns(2, gap="medium")

    with col3:
        _card_header("Workflow Status Funnel")
        status_counts = df.groupby("status").size().reset_index(name="count")
        status_order = ["reported", "assigned", "fixed"]
        status_counts["order"] = status_counts["status"].apply(
            lambda x: status_order.index(x) if x in status_order else 99
        )
        status_counts = status_counts.sort_values("order")
        status_colors = {"reported": TOKENS["reported"], "assigned": TOKENS["assigned"], "fixed": TOKENS["fixed"]}
        fig3 = go.Figure(go.Funnel(
            y=status_counts["status"].str.capitalize(),
            x=status_counts["count"],
            textinfo="value+percent initial",
            marker_color=[status_colors.get(s, TOKENS["muted"]) for s in status_counts["status"]],
        ))
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
            margin=dict(l=10, r=10, t=24, b=10),
            font=dict(family="Inter", size=13, color=TOKENS["navy"]),
        )
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    with col4:
        _card_header("Incidents Reported vs Resolved Over Time")
        fixed_df = df[df["status"] == "fixed"].copy()
        fixed_daily = fixed_df.groupby("date").size().reset_index(name="resolved") if not fixed_df.empty else pd.DataFrame(columns=["date", "resolved"])
        all_daily = df.groupby("date").size().reset_index(name="reported")
        merged = pd.merge(all_daily, fixed_daily, on="date", how="left").fillna(0)
        merged["date"] = pd.to_datetime(merged["date"])

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=merged["date"], y=merged["reported"],
            name="Reported", mode="lines+markers",
            line=dict(color=TOKENS["medium"], width=2.5),
            marker=dict(size=6),
        ))
        fig4.add_trace(go.Scatter(
            x=merged["date"], y=merged["resolved"],
            name="Resolved", mode="lines+markers",
            line=dict(color=TOKENS["teal_deep"], width=2.5),
            marker=dict(size=6),
        ))
        fig4.update_layout(xaxis_title="", yaxis_title="Hazards", hovermode="x unified")
        st.plotly_chart(_chart_layout(fig4), use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div style="margin-top:1.5rem"></div>', unsafe_allow_html=True)

    # ── Row 3: Avg Time to Fix | Top Hotspots by Area ─────────────────────────
    col5, col6 = st.columns(2, gap="medium")

    with col5:
        _card_header("Average Turnaround Time (Hours) by Category")
        fixed_df2 = df[df["status"] == "fixed"].copy()
        if not fixed_df2.empty and "updated_at" in fixed_df2.columns:
            fixed_df2["updated_at"] = pd.to_datetime(fixed_df2["updated_at"], errors="coerce")
            fixed_df2 = fixed_df2.dropna(subset=["updated_at"])
            if not fixed_df2.empty:
                fixed_df2["hours"] = (fixed_df2["updated_at"] - fixed_df2["created_at"]).dt.total_seconds() / 3600
                fixed_df2["hours"] = fixed_df2["hours"].apply(lambda h: max(h, 0.5))
                avg_by_type = fixed_df2.groupby("type")["hours"].mean().reset_index()
                avg_by_type["label"] = avg_by_type["type"].map(lambda x: ISSUE_LABELS.get(x, x))
                fig5 = px.bar(
                    avg_by_type, x="label", y="hours", color="label",
                    color_discrete_sequence=_PALETTE, text=avg_by_type["hours"].round(1),
                )
                fig5.update_traces(textposition="outside", marker_line_width=0)
                fig5.update_layout(showlegend=False, xaxis_title="", yaxis_title="Hours")
                st.plotly_chart(_chart_layout(fig5), use_container_width=True, config={"displayModeBar": False})
            else:
                empty_state("No turnaround history", "Resolution duration metrics will appear as issues are closed.")
        else:
            empty_state("No resolved issues", "Turnaround metrics will appear as work orders are closed.")

    with col6:
        _card_header("Top Municipal Hotspots by Neighborhood")
        hotspots = df.groupby("area").size().reset_index(name="count").nlargest(8, "count")
        fig6 = px.bar(
            hotspots, x="count", y="area", orientation="h",
            color="count", color_continuous_scale=["#6CC48A", "#136F63", "#0B2545"],
            text="count",
        )
        fig6.update_traces(textposition="outside")
        fig6.update_layout(
            showlegend=False, xaxis_title="Issue Volume", yaxis_title="",
            coloraxis_showscale=False, yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(_chart_layout(fig6, height=300), use_container_width=True, config={"displayModeBar": False})

    # ── Executive Weekly Operations Brief ─────────────────────────────────────
    st.markdown('<div style="margin-top:2.5rem"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="background:#FFFFFF;border:1px solid {TOKENS['border']};border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(11,37,69,0.04)">
          <div style="font-size:18px;font-weight:700;color:{TOKENS['navy']};margin-bottom:4px">
            Executive Weekly Operations Brief
          </div>
          <div style="font-size:14px;color:{TOKENS['muted']};margin-bottom:16px">
            Synthesize an executive operations summary directly from verified municipal data using Google Gemini.
          </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Generate Executive Operations Brief", key="gen_weekly_brief_btn", type="primary"):
        from core.ai_assess import generate_weekly_brief
        total_count = len(df)
        by_status = df["status"].value_counts().to_dict()
        by_sev = df["severity_label"].value_counts().to_dict()
        by_type = df["type"].value_counts().to_dict()
        top_areas = df["area"].value_counts().head(5).to_dict()

        avg_hrs = None
        if not fixed_df2.empty and "hours" in fixed_df2.columns:
            avg_hrs = round(float(fixed_df2["hours"].mean()), 1)

        stats_payload = {
            "total_issues_in_period": total_count,
            "status_breakdown": by_status,
            "severity_breakdown": by_sev,
            "hazard_type_counts": by_type,
            "top_hotspot_neighborhoods": top_areas,
            "average_time_to_fix_hours": avg_hrs,
        }

        with st.spinner("Synthesizing executive brief with Google Gemini…"):
            brief = generate_weekly_brief(stats_payload, actor=user)

        if brief:
            st.session_state["cached_weekly_brief"] = brief
            log_audit(user["username"], user["role"], "weekly_brief", None, f"Generated brief for {total_count} issues")
        else:
            st.warning("Brief synthesis unavailable (offline mode or API key inactive).")

    saved_brief = st.session_state.get("cached_weekly_brief")
    if saved_brief:
        st.markdown(
            f"""
            <div style="background:#F0F7F6;border-left:4px solid {TOKENS['teal_deep']};border-radius:8px;padding:20px;margin-top:16px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <span style="font-size:16px;font-weight:700;color:{TOKENS['navy']}">{saved_brief.title}</span>
                <span style="font-size:11px;background:#FFFFFF;color:{TOKENS['teal_deep']};padding:3px 8px;border-radius:4px;font-weight:700">Google Gemini AI</span>
              </div>
              <div style="font-size:14px;color:{TOKENS['navy']};line-height:1.6;margin-bottom:14px">
                {saved_brief.executive_summary}
              </div>
              <div style="margin-bottom:12px">
                <strong style="font-size:13px;color:{TOKENS['navy']}">Key Operational Takeaways:</strong>
                <ul style="font-size:13px;color:{TOKENS['navy']};margin-top:4px;padding-left:1.2rem">
                  {''.join(f'<li>{t}</li>' for t in saved_brief.key_takeaways)}
                </ul>
              </div>
              <div>
                <strong style="font-size:13px;color:{TOKENS['navy']}">Recommended Field Actions:</strong>
                <ul style="font-size:13px;color:{TOKENS['navy']};margin-top:4px;padding-left:1.2rem">
                  {''.join(f'<li>{a}</li>' for a in saved_brief.action_items)}
                </ul>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        md_content = (
            f"# {saved_brief.title}\n\n## Executive Summary\n{saved_brief.executive_summary}\n\n"
            f"## Key Takeaways\n" + "\n".join(f"- {t}" for t in saved_brief.key_takeaways) + "\n\n"
            f"## Action Items\n" + "\n".join(f"- {a}" for a in saved_brief.action_items)
        )
        st.download_button(
            "Download Brief (.md)",
            data=md_content,
            file_name="urbanlens_weekly_operations_brief.md",
            mime="text/markdown",
            key="download_brief_md",
        )

    st.markdown('</div>', unsafe_allow_html=True)
