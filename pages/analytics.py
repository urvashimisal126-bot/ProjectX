"""Analytics page — Admin and Officer only."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.auth import current_user, require_role
from core.db import list_issues, has_permission
from core.audit import log_audit
from ui.components import page_header, empty_state
from ui.theme import TOKENS


_PALETTE = [TOKENS["teal_deep"], TOKENS["teal"], TOKENS["mint"], TOKENS["navy"], TOKENS["medium"]]


def _chart_layout(fig, height: int = 300) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=0, r=0, t=24, b=0),
        font=dict(family="Inter", size=12, color=TOKENS["navy"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=TOKENS["border"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=TOKENS["border"], zeroline=False)
    return fig


def render() -> None:
    require_role(["admin", "officer"])
    user = current_user()

    page_header("Analytics", "Infrastructure issue trends, severity splits, and resolution metrics.")

    issues = list_issues(user)
    if not issues:
        empty_state("No data yet", "Submit some issue reports to see analytics.")
        return

    df = pd.DataFrame(issues)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date

    # ── Filter bar ─────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    with fc1:
        date_range = st.date_input(
            "Date range",
            value=[df["created_at"].min().date(), df["created_at"].max().date()],
            key="analytics_dates",
        )
    with fc2:
        from core.config import ISSUE_CLASSES, ISSUE_LABELS  # noqa: PLC0415
        f_type = st.multiselect("Issue type", ISSUE_CLASSES, format_func=lambda x: ISSUE_LABELS.get(x, x), key="an_type")
    with fc3:
        f_sev = st.multiselect("Severity", ["High", "Medium", "Low"], key="an_sev")

    if len(date_range) == 2:
        df = df[(df["date"] >= date_range[0]) & (df["date"] <= date_range[1])]
    if f_type:
        df = df[df["type"].isin(f_type)]
    if f_sev:
        df = df[df["severity_label"].isin(f_sev)]

    if df.empty:
        empty_state("No data in range", "Adjust filters to see results.")
        return

    st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)

    # ── Row 1: By type | Severity split ───────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        _card_header("Issues by Type")
        type_counts = df.groupby("type").size().reset_index(name="count")
        type_counts["label"] = type_counts["type"].map(lambda x: ISSUE_LABELS.get(x, x))
        fig = px.bar(
            type_counts, x="label", y="count", color="label",
            color_discrete_sequence=_PALETTE, text="count",
        )
        fig.update_traces(textposition="outside", marker_line_width=0)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(_chart_layout(fig), use_container_width=True, config={"displayModeBar": False})

    with col2:
        _card_header("Severity Distribution")
        sev_counts = df.groupby("severity_label").size().reset_index(name="count")
        sev_colors = {"High": TOKENS["high"], "Medium": TOKENS["medium"], "Low": TOKENS["low"]}
        fig2 = px.pie(
            sev_counts, names="severity_label", values="count",
            color="severity_label",
            color_discrete_map=sev_colors,
            hole=0.45,
        )
        fig2.update_traces(textinfo="label+percent", pull=[0.03] * len(sev_counts))
        fig2.update_layout(showlegend=False)
        st.plotly_chart(_chart_layout(fig2), use_container_width=True, config={"displayModeBar": False})

    # ── Row 2: Status funnel | Resolved over time ─────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        _card_header("Status Funnel")
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
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           height=300, margin=dict(l=0, r=0, t=24, b=0),
                           font=dict(family="Inter", size=12, color=TOKENS["navy"]))
        st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    with col4:
        _card_header("Issues Resolved Over Time")
        fixed_df = df[df["status"] == "fixed"].copy()
        if not fixed_df.empty:
            fixed_daily = fixed_df.groupby("date").size().reset_index(name="resolved")
            all_daily = df.groupby("date").size().reset_index(name="reported")
            merged = pd.merge(all_daily, fixed_daily, on="date", how="left").fillna(0)
            merged["date"] = pd.to_datetime(merged["date"])
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(
                x=merged["date"], y=merged["reported"],
                name="Reported", mode="lines+markers",
                line=dict(color=TOKENS["medium"], width=2),
                marker=dict(size=5),
            ))
            fig4.add_trace(go.Scatter(
                x=merged["date"], y=merged["resolved"],
                name="Resolved", mode="lines+markers",
                line=dict(color=TOKENS["teal_deep"], width=2),
                marker=dict(size=5),
            ))
            fig4.update_layout(xaxis_title="", yaxis_title="Issues", hovermode="x unified")
            st.plotly_chart(_chart_layout(fig4), use_container_width=True, config={"displayModeBar": False})
        else:
            empty_state("No resolved issues", "No fixed issues in the selected range.")

    # ── Row 3: Avg time-to-fix | Hotspot by area ─────────────────────────────
    col5, col6 = st.columns(2)

    with col5:
        _card_header("Avg. Time to Fix (hours) by Type")
        fixed_df2 = df[df["status"] == "fixed"].copy()
        if not fixed_df2.empty:
            fixed_df2["updated_at"] = pd.to_datetime(fixed_df2["updated_at"])
            fixed_df2["hours"] = (fixed_df2["updated_at"] - fixed_df2["created_at"]).dt.total_seconds() / 3600
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
            empty_state("No fixed issues", "Time-to-fix data will appear as issues are resolved.")

    with col6:
        _card_header("Top Issue Hotspots by Area")
        hotspots = df.groupby("area").size().reset_index(name="count").nlargest(10, "count")
        fig6 = px.bar(
            hotspots, x="count", y="area", orientation="h",
            color="count", color_continuous_scale=["#6CC48A", "#136F63", "#0B2545"],
            text="count",
        )
        fig6.update_traces(textposition="outside")
        fig6.update_layout(showlegend=False, xaxis_title="Issues", yaxis_title="",
                           coloraxis_showscale=False, yaxis=dict(autorange="reversed"))
        st.plotly_chart(_chart_layout(fig6, height=320), use_container_width=True, config={"displayModeBar": False})


def _card_header(title: str) -> None:
    st.markdown(
        f'<div style="font-size:13px;font-weight:700;color:{TOKENS["navy"]};margin-bottom:0.5rem">{title}</div>',
        unsafe_allow_html=True,
    )
