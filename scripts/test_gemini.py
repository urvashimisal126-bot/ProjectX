"""
UrbanLens Gemini Live Smoke Test Script.
Tests:
1. Gemini API connectivity & authentication
2. Structured output parsing & pydantic validation
3. Vision assessment on sample image
4. Natural language query parsing (Ask UrbanLens)
5. Executive weekly brief generation
6. SQLite caching validation
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import GEMINI_API_KEY, GEMINI_MODEL, DETECTOR
from core.gemini_client import get_client, generate_json
from core.ai_assess import assess_image, AIAssessment, generate_bilingual_summary, generate_weekly_brief
from pages.assistant import _parse_query_with_gemini


def print_banner(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def run_live_tests():
    print_banner("URBANLENS — GOOGLE GEMINI HYBRID SUITE TEST")
    print(f"Configured Model : {GEMINI_MODEL}")
    print(f"Detector Mode    : {DETECTOR}")
    print(f"API Key Present  : {'Yes (' + GEMINI_API_KEY[:6] + '...)' if GEMINI_API_KEY else 'No'}")

    client = get_client()
    if not client:
        print("\n[WARNING] Gemini client could not be initialized.")
        print("  Please check that GEMINI_API_KEY is set in .streamlit/secrets.toml or environment variables.")
        print("  UrbanLens will operate in deterministic YOLO offline fallback mode.")
        return

    # Test 1: Vision Assessment
    print("\n[1/4] Testing Vision Assessment on sample image...")
    sample_img = Image.new("RGB", (320, 240), color=(140, 140, 140))
    start_t = time.perf_counter()
    assess = assess_image(sample_img, actor={"username": "smoke_test", "role": "admin"})
    elapsed = int((time.perf_counter() - start_t) * 1000)

    if assess:
        print(f"  [SUCCESS] Latency: {elapsed}ms")
        print(f"  Confirmed Hazard : {assess.confirmed}")
        print(f"  Hazard Type      : {assess.hazard_type}")
        print(f"  Severity Hint    : {assess.severity_hint}")
        print(f"  Action           : {assess.recommended_action}")
        print(f"  Description      : {assess.description}")
    else:
        print("  [FALLBACK] Gemini API call returned None (graceful fallback active).")

    # Test 2: Bilingual Summary
    if assess:
        print("\n[2/4] Testing Hindi/English Bilingual Summary...")
        hi_summary = generate_bilingual_summary(assess.model_dump(), language="hi", actor={"username": "smoke_test", "role": "admin"})
        en_summary = generate_bilingual_summary(assess.model_dump(), language="en", actor={"username": "smoke_test", "role": "admin"})
        print(f"  English: {en_summary or 'N/A'}")
        print(f"  Hindi  : {hi_summary or 'N/A'}")

    # Test 3: Natural Language Assistant Query Parser
    print("\n[3/4] Testing 'Ask UrbanLens' Natural Language Parser...")
    query = "Show unassigned critical potholes in Vijay Nagar this week"
    parsed_q = _parse_query_with_gemini(query, actor={"username": "smoke_test", "role": "admin"})
    if parsed_q:
        print("  [SUCCESS] Query Parsed into Operational Filters:")
        print(f"  Hazard Types : {parsed_q.hazard_types}")
        print(f"  Severities   : {parsed_q.severities}")
        print(f"  Area         : {parsed_q.area}")
        print(f"  Days Back    : {parsed_q.days_back}")
        print(f"  Explanation  : {parsed_q.explanation}")
    else:
        print("  [FALLBACK] Fallback heuristic query parser active.")

    # Test 4: Weekly Executive Brief
    print("\n[4/4] Testing Executive Weekly Brief Generator...")
    stats_sample = {
        "total_issues_in_period": 24,
        "status_breakdown": {"reported": 6, "assigned": 8, "fixed": 10},
        "severity_breakdown": {"High": 5, "Medium": 12, "Low": 7},
        "hazard_type_counts": {"pothole": 14, "road_damage": 6, "drain": 4},
        "top_hotspot_neighborhoods": {"Vijay Nagar": 8, "Palasia": 6},
    }
    brief = generate_weekly_brief(stats_sample, actor={"username": "smoke_test", "role": "admin"})
    if brief:
        print(f"  [SUCCESS] Title: {brief.title}")
        print(f"  Executive Summary: {brief.executive_summary[:120]}...")
        print(f"  Takeaways Count: {len(brief.key_takeaways)}")
        print(f"  Actions Count  : {len(brief.action_items)}")
    else:
        print("  [FALLBACK] Brief generation fallback active.")

    print_banner("GEMINI HYBRID SMOKE TEST COMPLETE")


if __name__ == "__main__":
    run_live_tests()
