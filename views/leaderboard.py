"""
Citizen Leaderboard and Credits View.
Citizen-only feature recognizing active civic contributors across Indore.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import html

import core.db as db
import core.credits as credits
from core.config import CREDIT_RULES, CITIZEN_LEVELS, BADGE_DEFINITIONS


def render_leaderboard_view() -> None:
    """Main entrypoint for Citizen Leaderboard & Credits page."""
    user = st.session_state.get("user")
    if not user:
        st.warning("Please sign in to view the Citizen Leaderboard.")
        return

    # Role guard: Citizen only
    if user.get("role") != "citizen":
        st.info("The Citizen Leaderboard & Credits system is dedicated to active citizen reporters.")
        return

    # Fetch fresh user record
    current_user_record = db.get_user(user.get("username", "")) or user
    user_id = current_user_record.get("id", user.get("id"))
    username = current_user_record.get("username", "")

    # Page Header
    st.markdown(
        """
        <div style="margin-bottom: 1.5rem;">
            <h1 style="font-size: 26px; font-weight: 800; color: #0B2545; margin: 0 0 4px 0;">
                Citizen Leaderboard & Credits
            </h1>
            <p style="font-size: 15px; color: #5B6B7F; margin: 0;">
                Recognising civic engagement across Indore · Earn credits for verified reports
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3 Main Tabs
    tab_rankings, tab_my_credits, tab_rewards = st.tabs([
        "Leaderboard",
        "My Credits & Badges",
        "Perks & Certificate",
    ])

    with tab_rankings:
        _render_rankings_tab(current_user_record)

    with tab_my_credits:
        _render_my_credits_tab(user_id, username, current_user_record)

    with tab_rewards:
        _render_rewards_tab(user_id, username, current_user_record)


def _render_rankings_tab(user_record: dict) -> None:
    """Tab 1: Leaderboard rankings with podium, period filter, and privacy toggle."""
    user_id = user_record.get("id")
    username = user_record.get("username", "")

    col_top_left, col_top_right = st.columns([2, 1])

    with col_top_left:
        period_label = st.radio(
            "Ranking Period",
            options=["All Time", "This Month", "This Week"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )
    
    period_map = {
        "All Time": "all_time",
        "This Month": "this_month",
        "This Week": "this_week",
    }
    selected_period = period_map[period_label]

    with col_top_right:
        # Privacy Toggle
        current_show = bool(user_record.get("show_on_leaderboard", 1))
        new_show = st.toggle(
            "Show my name publicly",
            value=current_show,
            help="When toggled off, your name appears as 'Anonymous Citizen' to other users.",
        )
        if new_show != current_show:
            db.update_user_privacy(user_id, new_show)
            st.session_state["user"]["show_on_leaderboard"] = 1 if new_show else 0
            st.rerun()

    ranked_list = credits.get_ranked_leaderboard(current_username=username, period=selected_period)

    if not ranked_list:
        st.info("No verified citizen reports recorded for this period yet.")
        return

    # Top 3 Podium
    top_3 = ranked_list[:3]
    if top_3:
        st.markdown("<div style='margin-top: 1rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
        cols_podium = st.columns(3)

        podium_styles = [
            {"border": "#F59E0B", "badge_bg": "rgba(245, 158, 11, 0.12)", "badge_color": "#B45309", "title": "1st Place"},
            {"border": "#94A3B8", "badge_bg": "rgba(148, 163, 184, 0.15)", "badge_color": "#475569", "title": "2nd Place"},
            {"border": "#D97706", "badge_bg": "rgba(217, 119, 6, 0.12)", "badge_color": "#92400E", "title": "3rd Place"},
        ]

        for idx, citizen in enumerate(top_3):
            style = podium_styles[idx]
            is_me_badge = "<span style='background:#1B9C85; color:#fff; font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; margin-left:6px;'>You</span>" if citizen["is_me"] else ""
            
            with cols_podium[idx]:
                st.markdown(
                    f"""
                    <div style="background: #ffffff; border: 1.5px solid {style['border']}; border-radius: 12px; padding: 18px; text-align: center; box-shadow: 0 2px 8px rgba(11,37,69,0.05); height: 100%;">
                        <div style="display:inline-block; background:{style['badge_bg']}; color:{style['badge_color']}; font-size:12px; font-weight:700; padding:3px 10px; border-radius:16px; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.04em;">
                            {style['title']}
                        </div>
                        <div style="font-size: 17px; font-weight: 700; color: #0B2545; margin-bottom: 4px;">
                            {html.escape(citizen['display_name'])} {is_me_badge}
                        </div>
                        <div style="font-size: 13px; color: #136F63; font-weight: 600; margin-bottom: 12px;">
                            Level {citizen['level']} · {citizen['level_title']}
                        </div>
                        <div style="border-top: 1px solid #E3E8EF; padding-top: 10px; display: flex; justify-content: space-around;">
                            <div>
                                <div style="font-size: 18px; font-weight: 800; color: #0B2545;">{citizen['total_credits']}</div>
                                <div style="font-size: 11px; color: #5B6B7F; text-transform: uppercase;">Credits</div>
                            </div>
                            <div>
                                <div style="font-size: 18px; font-weight: 800; color: #1B9C85;">{citizen['verified_reports']}</div>
                                <div style="font-size: 11px; color: #5B6B7F; text-transform: uppercase;">Verified</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    # Full Leaderboard Table
    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin: 1.5rem 0 0.75rem 0;'>Full Civic Rankings</h3>", unsafe_allow_html=True)

    table_rows = []
    for row in ranked_list:
        is_me = row["is_me"]
        name_str = f"{row['display_name']} (You)" if is_me else row["display_name"]
        table_rows.append({
            "Rank": f"#{row['rank']}",
            "Citizen": name_str,
            "Level": f"Lvl {row['level']} · {row['level_title']}",
            "Verified Reports": row["verified_reports"],
            "Credits": row["total_credits"],
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank": st.column_config.TextColumn("Rank", width="small"),
            "Citizen": st.column_config.TextColumn("Citizen Contributor", width="medium"),
            "Level": st.column_config.TextColumn("Level", width="medium"),
            "Verified Reports": st.column_config.NumberColumn("Verified Reports", width="small"),
            "Credits": st.column_config.NumberColumn("Total Credits", width="small"),
        },
    )


def _render_my_credits_tab(user_id: int, username: str, user_record: dict) -> None:
    """Tab 2: Personal credit balance, level progression bar, badges, and ledger."""
    data = credits.get_citizen_dashboard_credits(user_id, username)
    level_info = data["level_info"]
    balance = data["balance"]
    verified_count = data["verified_count"]

    # Hero stats cards
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
            <div class="urban-card" style="margin-bottom:0; text-align:center;">
                <div style="font-size:12px; font-weight:700; color:#5B6B7F; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:4px;">
                    Civic Balance
                </div>
                <div style="font-size:32px; font-weight:800; color:#136F63; line-height:1.1;">
                    {balance}
                </div>
                <div style="font-size:13px; color:#5B6B7F; margin-top:4px;">
                    Available credits
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="urban-card" style="margin-bottom:0; text-align:center;">
                <div style="font-size:12px; font-weight:700; color:#5B6B7F; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:4px;">
                    Current Level
                </div>
                <div style="font-size:26px; font-weight:800; color:#0B2545; line-height:1.1;">
                    Level {level_info['level']}
                </div>
                <div style="font-size:13px; font-weight:600; color:#1B9C85; margin-top:4px;">
                    {level_info['title']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="urban-card" style="margin-bottom:0; text-align:center;">
                <div style="font-size:12px; font-weight:700; color:#5B6B7F; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:4px;">
                    Verified Reports
                </div>
                <div style="font-size:32px; font-weight:800; color:#0B2545; line-height:1.1;">
                    {verified_count}
                </div>
                <div style="font-size:13px; color:#5B6B7F; margin-top:4px;">
                    Verified submissions
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Progression Bar
    st.markdown("<div style='margin-top: 1.5rem;'>", unsafe_allow_html=True)
    next_title = level_info.get("next_title")
    if next_title:
        st.markdown(
            f"""
            <div style="background:#ffffff; border:1px solid #E3E8EF; border-radius:12px; padding:18px; margin-bottom:1.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:14px; font-weight:700; color:#0B2545;">
                        Level {level_info['level']}: {level_info['title']}
                    </span>
                    <span style="font-size:13px; font-weight:600; color:#136F63;">
                        Next: Level {level_info['level']+1} ({next_title}) · {level_info['credits_to_next']} credits needed
                    </span>
                </div>
                <div style="background:#E3E8EF; border-radius:8px; height:12px; overflow:hidden; width:100%;">
                    <div style="background:linear-gradient(90deg, #136F63, #1B9C85); height:100%; width:{level_info['progress_pct']}%; border-radius:8px; transition:width 0.4s ease;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:11px; color:#5B6B7F;">
                    <span>{level_info['min_credits']} credits</span>
                    <span>{level_info['progress_pct']}% completed</span>
                    <span>{level_info['max_credits']+1} credits</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background:rgba(27,156,133,0.1); border:1px solid #1B9C85; border-radius:12px; padding:16px; margin-bottom:1.5rem; text-align:center;">
                <span style="font-size:15px; font-weight:700; color:#136F63;">
                    Max Level Achieved · Civic Legend of Indore
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Badges Showcase
    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin-bottom: 0.75rem;'>Earned Badges</h3>", unsafe_allow_html=True)
    badge_cards = data["badge_cards"]
    cols_badges = st.columns(len(badge_cards))

    for idx, badge in enumerate(badge_cards):
        with cols_badges[idx]:
            earned = badge["earned"]
            border_color = "#1B9C85" if earned else "#E3E8EF"
            bg_color = "#ffffff" if earned else "#F8FAFC"
            title_color = "#0B2545" if earned else "#94A3B8"
            icon_color = "#136F63" if earned else "#94A3B8"
            status_text = f"Earned" if earned else "Locked"
            status_bg = "rgba(27, 156, 133, 0.12)" if earned else "rgba(148, 163, 184, 0.15)"
            status_color = "#136F63" if earned else "#64748B"

            st.markdown(
                f"""
                <div style="background:{bg_color}; border:1.5px solid {border_color}; border-radius:10px; padding:14px; text-align:center; height:100%;">
                    <div style="display:inline-block; background:{status_bg}; color:{status_color}; font-size:10px; font-weight:700; padding:2px 8px; border-radius:12px; margin-bottom:8px; text-transform:uppercase;">
                        {status_text}
                    </div>
                    <div style="font-size:14px; font-weight:700; color:{title_color}; margin-bottom:4px;">
                        {badge['title']}
                    </div>
                    <div style="font-size:11px; color:#5B6B7F; line-height:1.3;">
                        {badge['description']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Credit History Ledger
    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin: 1.75rem 0 0.75rem 0;'>Credit History Ledger</h3>", unsafe_allow_html=True)
    ledger = data["ledger"]
    if ledger:
        rows = []
        for entry in ledger:
            delta = entry["delta"]
            delta_str = f"+{delta}" if delta > 0 else f"{delta}"
            rows.append({
                "Date": entry["created_at"][:16],
                "Reason": entry["reason_code"].replace("_", " ").title(),
                "Issue ID": f"#{entry['issue_id']}" if entry.get("issue_id") else "-",
                "Change": delta_str,
                "Note": entry.get("note") or "",
            })
        df_ledger = pd.DataFrame(rows)
        st.dataframe(
            df_ledger,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date & Time", width="small"),
                "Reason": st.column_config.TextColumn("Activity", width="medium"),
                "Issue ID": st.column_config.TextColumn("Issue", width="small"),
                "Change": st.column_config.TextColumn("Credits", width="small"),
                "Note": st.column_config.TextColumn("Details", width="large"),
            },
        )
    else:
        st.info("No credit transactions recorded yet. Submit reports to earn credits once verified by city officers.")

    # Rules Information Callout
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E3E8EF; border-left:4px solid #136F63; border-radius:8px; padding:16px; margin-top:1.5rem;">
            <div style="font-size:14px; font-weight:700; color:#0B2545; margin-bottom:6px;">
                How Civic Credits Work
            </div>
            <div style="font-size:13px; color:#5B6B7F; line-height:1.5;">
                • <strong>+25 credits</strong> for every verified report verified by a city officer.<br/>
                • <strong>+15 bonus</strong> for high-severity hazards (deep potholes, open drains).<br/>
                • <strong>+50 welcome bonus</strong> on your first verified civic submission.<br/>
                • Maximum 5 verified credit awards per day to maintain quality and prevent spam.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_rewards_tab(user_id: int, username: str, user_record: dict) -> None:
    """Tab 3: Civic perks matrix, digital certificate generator, and municipal rewards."""
    data = credits.get_citizen_dashboard_credits(user_id, username)
    level_info = data["level_info"]
    current_level = level_info["level"]
    raw_name = user_record.get("name", "Citizen")

    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin-bottom: 0.75rem;'>Civic Tier Perks</h3>", unsafe_allow_html=True)

    perks = [
        {"lvl": 1, "title": "Neighbourhood Watch", "perk": "Public profile badge & community impact tracking", "unlocked": current_level >= 1},
        {"lvl": 2, "title": "Civic Scout", "perk": "Official Downloadable Certificate of Civic Appreciation from Indore Municipal Corporation", "unlocked": current_level >= 2},
        {"lvl": 3, "title": "Community Champion", "perk": "Priority triage flag in municipal dispatch queue", "unlocked": current_level >= 3},
        {"lvl": 4, "title": "City Guardian", "perk": "Invitation to Annual Indore Civic Town Hall & City Guardian lapel pin eligibility", "unlocked": current_level >= 4},
        {"lvl": 5, "title": "Civic Legend", "perk": "Mayor's Civic Excellence Roll of Honour recognition", "unlocked": current_level >= 5},
    ]

    for p in perks:
        status_badge = "<span style='background:rgba(27,156,133,0.12); color:#136F63; font-weight:700; font-size:11px; padding:3px 10px; border-radius:12px;'>UNLOCKED</span>" if p["unlocked"] else "<span style='background:rgba(148,163,184,0.15); color:#64748B; font-weight:700; font-size:11px; padding:3px 10px; border-radius:12px;'>LOCKED</span>"
        border = "#1B9C85" if p["unlocked"] else "#E3E8EF"
        opacity = "1" if p["unlocked"] else "0.7"

        st.markdown(
            f"""
            <div style="background:#ffffff; border:1px solid {border}; border-radius:10px; padding:14px 18px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; opacity:{opacity};">
                <div>
                    <div style="font-size:14px; font-weight:700; color:#0B2545;">
                        Level {p['lvl']}: {p['title']}
                    </div>
                    <div style="font-size:13px; color:#5B6B7F; margin-top:2px;">
                        {p['perk']}
                    </div>
                </div>
                <div>{status_badge}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Certificate Generation Section
    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin: 1.75rem 0 0.75rem 0;'>Civic Certificate of Appreciation</h3>", unsafe_allow_html=True)

    if current_level >= 2:
        st.markdown(
            """
            <p style="font-size:14px; color:#5B6B7F;">
                Congratulations! As an active contributor (Level 2 or above), you are eligible to download your official Indore UrbanLens Civic Certificate.
            </p>
            """,
            unsafe_allow_html=True,
        )

        cert_html = _generate_certificate_html(
            citizen_name=raw_name,
            level_title=level_info["title"],
            level_num=current_level,
            credits=data["balance"],
            verified_count=data["verified_count"],
        )

        with st.expander("Preview Certificate", expanded=True):
            st.components.v1.html(cert_html, height=480, scrolling=False)

        st.download_button(
            label="Download Certificate (HTML/Print)",
            data=cert_html,
            file_name=f"UrbanLens_Civic_Certificate_{username}.html",
            mime="text/html",
            type="primary",
        )
    else:
        st.info("Reach Level 2 (Civic Scout · 100+ credits) to unlock your official downloadable Certificate of Appreciation.")

    # Upcoming Municipal Perks Pilot
    st.markdown("<h3 style='font-size: 16px; font-weight: 700; color: #0B2545; margin: 1.75rem 0 0.75rem 0;'>Upcoming Municipal Partner Perks (Pilot)</h3>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:12px;">
            <div style="background:#ffffff; border:1px dashed #CBD5E1; border-radius:10px; padding:16px;">
                <div style="font-size:11px; font-weight:700; color:#136F63; text-transform:uppercase;">Proposed Pilot</div>
                <div style="font-size:14px; font-weight:700; color:#0B2545; margin:4px 0;">iBus Transit Pass Rebate</div>
                <div style="font-size:12px; color:#5B6B7F;">Redeem 200 credits for monthly AICTSL city bus pass voucher.</div>
            </div>
            <div style="background:#ffffff; border:1px dashed #CBD5E1; border-radius:10px; padding:16px;">
                <div style="font-size:11px; font-weight:700; color:#136F63; text-transform:uppercase;">Proposed Pilot</div>
                <div style="font-size:14px; font-weight:700; color:#0B2545; margin:4px 0;">Smart Parking Discount</div>
                <div style="font-size:12px; color:#5B6B7F;">15% discount on municipal multi-level parking in Rajwada & Vijay Nagar.</div>
            </div>
            <div style="background:#ffffff; border:1px dashed #CBD5E1; border-radius:10px; padding:16px;">
                <div style="font-size:11px; font-weight:700; color:#136F63; text-transform:uppercase;">Proposed Pilot</div>
                <div style="font-size:14px; font-weight:700; color:#0B2545; margin:4px 0;">Tree Plantation in Your Name</div>
                <div style="font-size:12px; color:#5B6B7F;">Municipal corporation plants a native sapling for Level 4+ Guardians.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _generate_certificate_html(citizen_name: str, level_title: str, level_num: int, credits: int, verified_count: int) -> str:
    """Generate printable HTML certificate with modern official styling."""
    from datetime import datetime
    issue_date = datetime.now().strftime("%B %d, %Y")
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0;
    padding: 24px;
    background: #F8FAFC;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0B2545;
  }}
  .cert-container {{
    max-width: 720px;
    margin: 0 auto;
    background: #FFFFFF;
    border: 8px double #136F63;
    border-radius: 12px;
    padding: 36px 40px;
    box-shadow: 0 4px 16px rgba(11,37,69,0.08);
    text-align: center;
    position: relative;
  }}
  .cert-header {{
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #136F63;
    margin-bottom: 8px;
  }}
  .cert-title {{
    font-size: 28px;
    font-weight: 800;
    color: #0B2545;
    margin: 0 0 16px 0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  .cert-presented {{
    font-size: 14px;
    color: #5B6B7F;
    margin-bottom: 8px;
  }}
  .cert-name {{
    font-size: 26px;
    font-weight: 700;
    color: #136F63;
    border-bottom: 2px solid #E3E8EF;
    display: inline-block;
    padding: 0 32px 6px 32px;
    margin-bottom: 16px;
  }}
  .cert-body {{
    font-size: 14px;
    line-height: 1.6;
    color: #334155;
    max-width: 580px;
    margin: 0 auto 24px auto;
  }}
  .cert-stats {{
    display: flex;
    justify-content: center;
    gap: 36px;
    background: #F1F5F9;
    border-radius: 8px;
    padding: 12px 24px;
    max-width: 440px;
    margin: 0 auto 28px auto;
  }}
  .stat-val {{
    font-size: 18px;
    font-weight: 800;
    color: #0B2545;
  }}
  .stat-lbl {{
    font-size: 11px;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
  }}
  .cert-footer {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #E2E8F0;
    font-size: 12px;
    color: #64748B;
  }}
</style>
</head>
<body>
  <div class="cert-container">
    <div class="cert-header">Indore Smart City · UrbanLens Civic Platform</div>
    <div class="cert-title">Certificate of Civic Recognition</div>
    <div class="cert-presented">This certificate is proudly awarded to</div>
    <div class="cert-name">{html.escape(citizen_name)}</div>
    <div class="cert-body">
      In recognition of outstanding active citizenship and dedication to improving Indore's urban infrastructure through verified community reports and high civic engagement.
    </div>
    <div class="cert-stats">
      <div>
        <div class="stat-val">Level {level_num}</div>
        <div class="stat-lbl">{level_title}</div>
      </div>
      <div>
        <div class="stat-val">{verified_count}</div>
        <div class="stat-lbl">Verified Reports</div>
      </div>
      <div>
        <div class="stat-val">{credits}</div>
        <div class="stat-lbl">Civic Credits</div>
      </div>
    </div>
    <div class="cert-footer">
      <div style="text-align:left;">
        <div><strong>Date of Issue:</strong> {issue_date}</div>
        <div>UrbanLens Civic Protocol</div>
      </div>
      <div style="text-align:right;">
        <div style="font-weight:700; color:#0B2545;">Indore Municipal Corporation</div>
        <div>Civic Engagement Division</div>
      </div>
    </div>
  </div>
</body>
</html>"""
