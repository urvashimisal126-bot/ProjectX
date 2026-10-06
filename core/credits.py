"""
Credits, Badges, and Citizen Gamification Engine for UrbanLens.
Enforces role boundaries, anti-abuse caps, append-only credit ledger transactions,
and privacy-safe leaderboard presentation.
"""

from __future__ import annotations

import json
from typing import Any

from core.config import (
    CREDIT_RULES,
    CITIZEN_LEVELS,
    BADGE_DEFINITIONS,
    DAILY_CREDIT_REPORT_CAP,
    MAX_STRIKES_ALLOWED,
)
import core.db as db
from core.audit import log_audit


def get_user_level(credits_balance: int) -> dict:
    """Compute citizen level, tier title, and progress percentage."""
    credits_balance = max(0, credits_balance)
    current_level = CITIZEN_LEVELS[0]
    next_level = None

    for i, lvl in enumerate(CITIZEN_LEVELS):
        if credits_balance >= lvl["min_credits"]:
            current_level = lvl
            if i + 1 < len(CITIZEN_LEVELS):
                next_level = CITIZEN_LEVELS[i + 1]
            else:
                next_level = None

    if next_level:
        span = next_level["min_credits"] - current_level["min_credits"]
        progress = credits_balance - current_level["min_credits"]
        pct = min(100.0, max(0.0, (progress / span) * 100.0))
        credits_to_next = next_level["min_credits"] - credits_balance
    else:
        pct = 100.0
        credits_to_next = 0

    return {
        "level": current_level["level"],
        "title": current_level["title"],
        "min_credits": current_level["min_credits"],
        "max_credits": current_level["max_credits"],
        "credits": credits_balance,
        "next_title": next_level["title"] if next_level else None,
        "credits_to_next": credits_to_next,
        "progress_pct": round(pct, 1),
    }


def format_display_name(raw_name: str, show_on_leaderboard: bool = True, is_current_user: bool = False) -> str:
    """Format name for leaderboard privacy: 'First Name + Last Initial' or 'Anonymous Citizen'."""
    if not show_on_leaderboard and not is_current_user:
        return "Anonymous Citizen"

    clean = raw_name.strip()
    if not clean:
        return "Anonymous Citizen"

    parts = clean.split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def get_reporter_trust_tier(verified_count: int, strikes: int = 0, suspended: bool = False) -> dict:
    """Return trust signal badge data for officers reviewing reports."""
    if suspended or strikes >= MAX_STRIKES_ALLOWED:
        return {
            "tier": "Suspended / High Risk",
            "badge_color": "#EF4444",
            "badge_bg": "rgba(239, 68, 68, 0.12)",
            "icon": "warning",
            "description": f"Account has {strikes} strikes. Flagged for review.",
        }
    if verified_count >= 10:
        return {
            "tier": "Trusted Reporter",
            "badge_color": "#1B9C85",
            "badge_bg": "rgba(27, 156, 133, 0.12)",
            "icon": "verified",
            "description": f"{verified_count} verified reports. Highly reliable.",
        }
    if verified_count >= 3:
        return {
            "tier": "Regular Contributor",
            "badge_color": "#2563EB",
            "badge_bg": "rgba(37, 99, 235, 0.12)",
            "icon": "thumb_up",
            "description": f"{verified_count} verified reports.",
        }
    return {
        "tier": "New Reporter",
        "badge_color": "#64748B",
        "badge_bg": "rgba(100, 116, 139, 0.12)",
        "icon": "person",
        "description": "First few reports. Standard review required.",
    }


def verify_and_reward_report(actor: dict, issue_id: int) -> dict:
    """
    Officer or Admin verifies a report.
    Applies anti-abuse rules, awards credits to citizen reporter, and evaluates badge unlocks.
    """
    # 1. Update issue verification status in DB
    updated_issue = db.verify_issue_db(actor, issue_id)
    reporter_username = updated_issue.get("reported_by", "")

    reporter_user = db.get_user(reporter_username) if reporter_username else None
    rewards_awarded: list[dict] = []
    badges_awarded: list[str] = []

    # Only citizens earn credits (officers and admins do not)
    if reporter_user and reporter_user.get("role") == "citizen":
        user_id = reporter_user["id"]
        strikes = reporter_user.get("strikes", 0)
        is_suspended = reporter_user.get("rewards_suspended", 0) == 1 or strikes >= MAX_STRIKES_ALLOWED

        if not is_suspended:
            # Check daily report reward cap
            daily_count = db.get_user_daily_credits_count(user_id)
            if daily_count >= DAILY_CREDIT_REPORT_CAP:
                db.add_credit_ledger_entry(
                    user_id=user_id,
                    delta=0,
                    reason_code="DAILY_CAP_REACHED",
                    issue_id=issue_id,
                    note=f"Daily credit cap ({DAILY_CREDIT_REPORT_CAP} reports/day) reached.",
                    created_by=actor.get("username", "system"),
                )
            else:
                # 1. Base verification reward
                base_delta = CREDIT_RULES["REPORT_VERIFIED"]
                db.add_credit_ledger_entry(
                    user_id=user_id,
                    delta=base_delta,
                    reason_code="REPORT_VERIFIED",
                    issue_id=issue_id,
                    note=f"Report #{issue_id} verified by {actor.get('username')}",
                    created_by=actor.get("username", "system"),
                )
                rewards_awarded.append({"code": "REPORT_VERIFIED", "delta": base_delta})

                # 2. High severity bonus
                if updated_issue.get("severity_label") == "High":
                    high_delta = CREDIT_RULES["HIGH_SEVERITY_BONUS"]
                    db.add_credit_ledger_entry(
                        user_id=user_id,
                        delta=high_delta,
                        reason_code="HIGH_SEVERITY_BONUS",
                        issue_id=issue_id,
                        note=f"High severity issue bonus for #{issue_id}",
                        created_by=actor.get("username", "system"),
                    )
                    rewards_awarded.append({"code": "HIGH_SEVERITY_BONUS", "delta": high_delta})

                # 3. Check for First Report Bonus
                verified_count = db.get_user_verified_reports_count(reporter_username)
                if verified_count == 1:
                    first_delta = CREDIT_RULES["FIRST_REPORT_BONUS"]
                    db.add_credit_ledger_entry(
                        user_id=user_id,
                        delta=first_delta,
                        reason_code="FIRST_REPORT_BONUS",
                        issue_id=issue_id,
                        note="Welcome bonus: First verified civic report!",
                        created_by=actor.get("username", "system"),
                    )
                    rewards_awarded.append({"code": "FIRST_REPORT_BONUS", "delta": first_delta})

            # Check and trigger badge evaluations
            badges_awarded = evaluate_and_grant_badges(user_id, reporter_username)

    # Log audit trail
    total_delta = sum(r["delta"] for r in rewards_awarded)
    log_audit(
        username=actor.get("username", "system"),
        role=actor.get("role", "officer"),
        action="verify_issue",
        issue_id=issue_id,
        detail=f"Verified report #{issue_id}. Awarded {total_delta} credits to {reporter_username}.",
    )

    return {
        "issue": updated_issue,
        "rewards_awarded": rewards_awarded,
        "total_credits_awarded": total_delta,
        "badges_awarded": badges_awarded,
    }


def reject_and_penalize_report(
    actor: dict, issue_id: int, reason: str, apply_strike: bool = False
) -> dict:
    """Officer rejects a bogus or invalid report, with optional penalty/strike."""
    updated_issue = db.reject_issue_db(actor, issue_id, reason)
    reporter_username = updated_issue.get("reported_by", "")
    reporter_user = db.get_user(reporter_username) if reporter_username else None

    penalty_applied = False
    if reporter_user and apply_strike and reporter_user.get("role") == "citizen":
        user_id = reporter_user["id"]
        current_strikes = reporter_user.get("strikes", 0) + 1
        is_suspended = current_strikes >= MAX_STRIKES_ALLOWED

        db.update_user_strikes(actor, user_id, current_strikes, is_suspended)
        penalty_delta = CREDIT_RULES["PENALTY_SPAM"]
        db.add_credit_ledger_entry(
            user_id=user_id,
            delta=penalty_delta,
            reason_code="PENALTY_SPAM",
            issue_id=issue_id,
            note=f"Penalty for invalid submission #{issue_id}: {reason}",
            created_by=actor.get("username", "system"),
        )
        penalty_applied = True

    log_audit(
        username=actor.get("username", "system"),
        role=actor.get("role", "officer"),
        action="reject_issue",
        issue_id=issue_id,
        detail=f"Rejected report #{issue_id}. Reason: {reason}. Strike applied: {penalty_applied}",
    )

    return {
        "issue": updated_issue,
        "penalty_applied": penalty_applied,
    }


def evaluate_and_grant_badges(user_id: int, username: str) -> list[str]:
    """Check qualification criteria for all badges and grant missing ones."""
    earned_badges: list[str] = []
    verified_count = db.get_user_verified_reports_count(username)
    balance = db.get_user_credits_balance(user_id)
    level_info = get_user_level(balance)

    # 1. FIRST_STEP: 1+ verified report
    if verified_count >= 1:
        if db.award_badge_db(user_id, "FIRST_STEP", json.dumps({"verified_count": verified_count})):
            earned_badges.append("FIRST_STEP")

    # 2. COMMUNITY_HERO: 10+ verified reports
    if verified_count >= 10:
        if db.award_badge_db(user_id, "COMMUNITY_HERO", json.dumps({"verified_count": verified_count})):
            earned_badges.append("COMMUNITY_HERO")

    # 3. CENTURION: 100+ credits
    if balance >= 100:
        if db.award_badge_db(user_id, "CENTURION", json.dumps({"balance": balance})):
            earned_badges.append("CENTURION")

    # 4. MASTER_GUARDIAN: Level 4 or above
    if level_info["level"] >= 4:
        if db.award_badge_db(user_id, "MASTER_GUARDIAN", json.dumps({"level": level_info["level"]})):
            earned_badges.append("MASTER_GUARDIAN")

    # 5. ROAD_WARRIOR: 5+ verified pothole / road defect reports
    with db.get_conn() as conn:
        potholes = conn.execute(
            """SELECT COUNT(*) as n FROM issues 
               WHERE reported_by=? AND verification_status='verified' AND LOWER(type) LIKE '%pothole%'""",
            (username,),
        ).fetchone()
        if potholes and potholes["n"] >= 5:
            if db.award_badge_db(user_id, "ROAD_WARRIOR", json.dumps({"potholes": potholes["n"]})):
                earned_badges.append("ROAD_WARRIOR")

    return earned_badges


def get_citizen_dashboard_credits(user_id: int, username: str) -> dict:
    """Aggregate complete gamification profile for the Citizen Leaderboard & Credits page."""
    balance = db.get_user_credits_balance(user_id)
    level_info = get_user_level(balance)
    ledger = db.get_user_credit_ledger(user_id, limit=50)
    badges = db.get_user_badges(user_id)
    verified_count = db.get_user_verified_reports_count(username)

    # Build badge lookup with definition metadata
    badge_lookup = {b["badge_key"]: b for b in badges}
    badge_cards = []
    for key, defn in BADGE_DEFINITIONS.items():
        is_earned = key in badge_lookup
        badge_cards.append({
            "key": key,
            "title": defn["title"],
            "description": defn["description"],
            "icon": defn["icon"],
            "earned": is_earned,
            "awarded_at": badge_lookup[key]["awarded_at"] if is_earned else None,
        })

    return {
        "balance": balance,
        "level_info": level_info,
        "ledger": ledger,
        "badge_cards": badge_cards,
        "verified_count": verified_count,
    }


def get_ranked_leaderboard(current_username: str | None = None, period: str = "all_time") -> list[dict]:
    """Return ranked list of citizens for display on the public leaderboard."""
    raw_list = db.get_leaderboard_data(period=period)
    ranked: list[dict] = []

    for rank_idx, row in enumerate(raw_list, start=1):
        is_me = (current_username is not None and row["username"] == current_username)
        display_name = format_display_name(
            raw_name=row["name"],
            show_on_leaderboard=bool(row["show_on_leaderboard"]),
            is_current_user=is_me,
        )
        total_creds = int(row["total_credits"])
        lvl = get_user_level(total_creds)
        period_creds = int(row["period_credits"])

        ranked.append({
            "rank": rank_idx,
            "user_id": row["user_id"],
            "username": row["username"],
            "display_name": display_name,
            "level": lvl["level"],
            "level_title": lvl["title"],
            "verified_reports": int(row["verified_reports"]),
            "period_credits": period_creds,
            "total_credits": total_creds,
            "is_me": is_me,
            "show_on_leaderboard": bool(row["show_on_leaderboard"]),
            "strikes": row["strikes"],
        })

    return ranked
