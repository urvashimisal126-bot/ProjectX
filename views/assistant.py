"""Ask UrbanLens — Natural-Language Municipal Operations Assistant (Admin & Officer only)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal

import streamlit as st
import pandas as pd
from pydantic import BaseModel, Field

from core.auth import current_user, require_role
from core.config import ISSUE_CLASSES, ISSUE_LABELS, INDORE_AREAS, GEMINI_MODEL
from core.db import list_issues, has_permission
from core.gemini_client import generate_json
from core.audit import log_audit
from ui.components import page_header, severity_badge, status_badge, relative_time, empty_state
from ui.theme import TOKENS


class QueryFilterParams(BaseModel):
    hazard_types: list[str] = Field(default=[], description="List of hazard types: pothole, road_damage, streetlight, drain")
    severities: list[str] = Field(default=[], description="List of severities: High, Medium, Low")
    statuses: list[str] = Field(default=[], description="List of statuses: reported, assigned, fixed")
    area: str | None = Field(default=None, description="Specific Indore neighborhood/area if mentioned")
    assigned_to: str | None = Field(default=None, description="Assigned officer username if mentioned (or 'unassigned')")
    near_location_type: str | None = Field(default=None, description="Location type: school, hospital, highway, default")
    days_back: int | None = Field(default=None, description="Number of days to look back if time range mentioned (e.g. 7 for 'this week')")
    explanation: str = Field(description="1 concise sentence explaining what filters were extracted")


def _parse_query_with_gemini(user_query: str, actor: dict) -> QueryFilterParams | None:
    prompt = f"""
You are the query interpreter for UrbanLens municipal operations system.
Extract structured search parameters from the user's natural language question.

User query: "{user_query}"

Allowed Values:
- hazard_types: subset of ["pothole", "road_damage", "streetlight", "drain"]
- severities: subset of ["High", "Medium", "Low"]
- statuses: subset of ["reported", "assigned", "fixed"]
- areas: subset of {INDORE_AREAS}
- near_location_type: "school", "hospital", "highway", or null
- assigned_to: specific officer username or "unassigned" if user asks for unassigned/unallocated issues.

Instructions:
1. Map colloquial terms to standard enums (e.g. 'broken lights' -> 'streetlight', 'critical/urgent' -> 'High', 'open' -> 'reported').
2. If the user mentions 'this week', set days_back=7. If 'today', set days_back=1.
3. If no specific filter is requested for a dimension, return an empty list or null.
4. Provide a 1-sentence plain explanation of what you extracted.
5. Never execute or generate SQL.
"""
    return generate_json(
        prompt=prompt,
        schema=QueryFilterParams,
        feature="ask_assistant",
        actor=actor,
    )


def render() -> None:
    require_role(["admin", "officer"])
    user = current_user()

    page_header(
        "Ask UrbanLens",
        "Natural-language civic queries translated into live, role-checked operational filters.",
    )

    # Example query suggestions
    examples = [
        "Unassigned high severity potholes this week",
        "All broken streetlights in Vijay Nagar",
        "Open drains near schools and hospitals",
        "Fixed road damage reports in Palasia",
    ]

    st.markdown(f'<div style="font-size:12px;color:{TOKENS["muted"]};margin-bottom:0.5rem">Suggested Queries:</div>', unsafe_allow_html=True)
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        with cols[i]:
            if st.button(ex, key=f"ex_btn_{i}", use_container_width=True):
                st.session_state["assistant_query_input"] = ex
                st.session_state["execute_assistant_query"] = True

    query_input = st.text_input(
        "Enter your civic question:",
        value=st.session_state.get("assistant_query_input", ""),
        placeholder="e.g. show unassigned high severity potholes near schools",
        key="assistant_query_box",
    )

    should_run = st.button("Search & Analyze", type="primary", key="run_ask_btn") or st.session_state.pop("execute_assistant_query", False)

    if should_run and query_input.strip():
        user_query = query_input.strip()
        with st.spinner("Interpreting query with Google Gemini…"):
            parsed = _parse_query_with_gemini(user_query, actor=user)

        log_audit(
            user["username"],
            user["role"],
            "assistant_query",
            None,
            f"query='{user_query[:60]}' parsed={'yes' if parsed else 'fallback'}",
        )

        # Fallback heuristic parser if Gemini is unavailable
        if parsed is None:
            q_lower = user_query.lower()
            types_found = [t for t in ISSUE_CLASSES if t in q_lower or (t == "pothole" and "potholes" in q_lower) or (t == "streetlight" and "light" in q_lower) or (t == "drain" and "drain" in q_lower)]
            sev_found = ["High"] if any(w in q_lower for w in ["high", "critical", "urgent", "severe"]) else ([] if not any(w in q_lower for w in ["medium", "low"]) else ["Medium", "Low"])
            stat_found = ["reported"] if "unassigned" in q_lower or "open" in q_lower else []
            loc_type = "school" if "school" in q_lower else ("hospital" if "hospital" in q_lower else ("highway" if "highway" in q_lower else None))
            area_found = next((a for a in INDORE_AREAS if a.lower() in q_lower), None)

            parsed = QueryFilterParams(
                hazard_types=types_found,
                severities=sev_found,
                statuses=stat_found,
                area=area_found,
                assigned_to="unassigned" if "unassigned" in q_lower else None,
                near_location_type=loc_type,
                days_back=7 if "week" in q_lower else (1 if "today" in q_lower else None),
                explanation="Applied local keyword matching (Gemini offline/fallback mode).",
            )

        st.session_state["parsed_assistant_query"] = parsed

    parsed_result = st.session_state.get("parsed_assistant_query")
    if not parsed_result:
        empty_state("No query run yet", "Type a question above or select an example to query the live repair database.")
        return

    # ── Display Interpreted Filter Chips ──────────────────────────────────────
    chips = []
    if parsed_result.hazard_types:
        chips.append(f"Type: {', '.join(parsed_result.hazard_types)}")
    if parsed_result.severities:
        chips.append(f"Severity: {', '.join(parsed_result.severities)}")
    if parsed_result.statuses:
        chips.append(f"Status: {', '.join(parsed_result.statuses)}")
    if parsed_result.area:
        chips.append(f"Area: {parsed_result.area}")
    if parsed_result.near_location_type:
        chips.append(f"Near: {parsed_result.near_location_type}")
    if parsed_result.assigned_to:
        chips.append(f"Assignment: {parsed_result.assigned_to}")
    if parsed_result.days_back:
        chips.append(f"Timeframe: Last {parsed_result.days_back} days")

    chip_html = " ".join(
        f'<span style="background:#edf3fb;color:#2F6FB5;border:1px solid #c7dcfa;border-radius:12px;padding:3px 10px;font-size:11px;font-weight:600;margin-right:6px">{c}</span>'
        for c in chips
    ) or '<span style="color:#5B6B7F;font-size:12px">All records (unrestricted)</span>'

    st.markdown(
        f"""
        <div style="background:#FAFBFD;border:1px solid {TOKENS['border']};border-radius:8px;padding:1rem;margin:1rem 0">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem">
            <span style="font-size:12px;font-weight:700;color:{TOKENS['navy']};text-transform:uppercase">Interpreted Query Filter</span>
            <span style="font-size:11px;color:{TOKENS['muted']}">Google {GEMINI_MODEL}</span>
          </div>
          <div style="margin-bottom:0.5rem">{chip_html}</div>
          <div style="font-size:12px;color:{TOKENS['muted']}"><em>{parsed_result.explanation}</em></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Execute Safe DB Query ─────────────────────────────────────────────────
    db_filters = {}
    if parsed_result.hazard_types:
        db_filters["types"] = parsed_result.hazard_types
    if parsed_result.severities:
        db_filters["severities"] = parsed_result.severities
    if parsed_result.statuses:
        db_filters["statuses"] = parsed_result.statuses
    if parsed_result.area:
        db_filters["search"] = parsed_result.area

    # Query through backend RBAC enforcement
    matched_issues = list_issues(actor=user, filters=db_filters)

    # In-memory post-filters for assignment and location type
    if parsed_result.assigned_to == "unassigned":
        matched_issues = [i for i in matched_issues if not i.get("assigned_to")]
    elif parsed_result.assigned_to:
        matched_issues = [i for i in matched_issues if i.get("assigned_to") == parsed_result.assigned_to]

    if parsed_result.near_location_type:
        matched_issues = [i for i in matched_issues if i.get("location_type") == parsed_result.near_location_type]

    if parsed_result.days_back:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=parsed_result.days_back)).strftime("%Y-%m-%d %H:%M:%S")
        matched_issues = [i for i in matched_issues if i.get("created_at", "") >= cutoff]

    count = len(matched_issues)

    # ── Display Natural Language Answer & Result Count ────────────────────────
    st.markdown(
        f"""
        <div style="font-size:15px;font-weight:600;color:{TOKENS['navy']};margin:1.25rem 0 0.5rem">
          Found <span style="color:{TOKENS['deep_teal']};font-size:18px">{count}</span> matching issue{'s' if count != 1 else ''} in the system.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not matched_issues:
        st.info("No matching issues found for this query.")
        return

    # Table display
    table_rows = []
    for iss in matched_issues:
        table_rows.append({
            "ID": f"#{iss['id']}",
            "Type": ISSUE_LABELS.get(iss["type"], iss["type"]),
            "Severity": iss["severity_label"],
            "Priority": f"{iss['priority']:.3f}",
            "Status": iss["status"].capitalize(),
            "Area": iss.get("area", "—"),
            "Location Type": iss.get("location_type", "default"),
            "Assigned To": iss.get("assigned_to") or "Unassigned",
            "Reported": relative_time(iss["created_at"]),
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Detail viewer selector
    st.markdown('<div style="margin-top:1rem"></div>', unsafe_allow_html=True)
    c_sel, c_btn = st.columns([3, 1])
    with c_sel:
        issue_options = {f"#{i['id']} — {ISSUE_LABELS.get(i['type'], i['type'])} ({i.get('area','Unknown')})": i["id"] for i in matched_issues}
        chosen = st.selectbox("Inspect an issue in detail:", options=list(issue_options.keys()), key="assistant_pick_issue")
    with c_btn:
        if st.button("Open Issue Detail", key="assistant_open_btn", type="primary"):
            st.session_state["detail_issue_id"] = issue_options[chosen]
            st.session_state["current_page"] = "pages/issue_detail.py"
            st.rerun()
