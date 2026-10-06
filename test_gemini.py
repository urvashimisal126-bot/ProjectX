"""
Comprehensive unit test suite for Gemini integration, hybrid detector,
bilingual summaries, assistant query parser, and fallback handling.
All Gemini calls are mocked for deterministic local CI/CD execution.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from core.ai_assess import (
    AIAssessment, HazardTypeEnum, SeverityHintEnum, BoundingBox,
    assess_image, generate_bilingual_summary, generate_weekly_brief,
    WeeklyBriefReport, BilingualSummary
)
from core.gemini_client import generate_json, _compute_cache_key
from core.detect import detect_image_pil, DetectionResult, Detection
from core.score import compute_severity, compute_priority, severity_breakdown
from core.db import init_db, has_permission
from pages.assistant import QueryFilterParams, _parse_query_with_gemini


class TestGeminiIntegration(unittest.TestCase):

    def setUp(self):
        init_db()
        self.admin_user = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        self.officer_user = {"id": 2, "username": "officer1", "name": "Officer 1", "role": "officer"}
        self.citizen_user = {"id": 3, "username": "citizen1", "name": "Citizen 1", "role": "citizen"}
        self.guest_user = {"id": 0, "username": "guest", "name": "Guest", "role": "guest"}

    def test_schema_validation_success(self):
        valid_json = {
            "confirmed": True,
            "hazard_type": "pothole",
            "severity_hint": "high",
            "risk_to_public": "Severe hazard to fast-moving vehicles.",
            "description": "Deep asphalt depression roughly 40 cm wide.",
            "recommended_action": "Cold-mix asphalt patching.",
            "urgency_reason": "High traffic arterial corridor.",
            "agrees_with_yolo": True,
            "boxes": [{"label": "pothole", "box_2d": [200, 200, 600, 600]}],
        }
        obj = AIAssessment.model_validate(valid_json)
        self.assertTrue(obj.confirmed)
        self.assertEqual(obj.hazard_type, HazardTypeEnum.pothole)
        self.assertEqual(obj.severity_hint, SeverityHintEnum.high)
        self.assertEqual(len(obj.boxes), 1)

    def test_schema_validation_malformed_rejected(self):
        invalid_json = {
            "confirmed": "not_a_bool",
            "hazard_type": "unknown_hazard_type_xyz",
        }
        with self.assertRaises(Exception):
            AIAssessment.model_validate(invalid_json)

    @patch("core.gemini_client.get_client")
    def test_no_key_fallback(self, mock_get_client):
        mock_get_client.return_value = None
        img = Image.new("RGB", (100, 100), color=(100, 100, 100))
        res = assess_image(img, actor=self.admin_user)
        self.assertIsNone(res)

    @patch("core.gemini_client.get_client")
    def test_timeout_and_error_handling(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")
        mock_get_client.return_value = mock_client

        img = Image.new("RGB", (100, 100), color=(100, 100, 100))
        res = assess_image(img, actor=self.admin_user)
        self.assertIsNone(res)

    @patch("core.gemini_client.get_client")
    def test_cache_hit(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "confirmed": True,
            "hazard_type": "drain",
            "severity_hint": "medium",
            "risk_to_public": "Clogged storm drain causing localized pooling.",
            "description": "Debris accumulation at curb intake.",
            "recommended_action": "Desilting and grate clearing.",
            "urgency_reason": "Monsoon readiness priority.",
            "agrees_with_yolo": True,
            "boxes": [],
        })
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        img = Image.new("RGB", (100, 100), color=(50, 50, 50))
        # First call hits mock
        res1 = assess_image(img, actor=self.admin_user)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.hazard_type, HazardTypeEnum.drain)

        # Second call should retrieve from SQLite gemini_cache without calling mock_client
        mock_client.models.generate_content.reset_mock()
        res2 = assess_image(img, actor=self.admin_user)
        self.assertIsNotNone(res2)
        mock_client.models.generate_content.assert_not_called()

    @patch("core.detect.assess_image")
    def test_hybrid_mode_with_gemini_fallback(self, mock_assess):
        mock_assess.return_value = AIAssessment(
            confirmed=True,
            hazard_type=HazardTypeEnum.streetlight,
            severity_hint=SeverityHintEnum.medium,
            risk_to_public="Dark junction posing safety risk.",
            description="Pole luminaire inactive.",
            recommended_action="Replace 70W LED fixture.",
            urgency_reason="Nighttime intersection safety.",
            agrees_with_yolo=False,
            boxes=[BoundingBox(label="streetlight", box_2d=[100, 400, 500, 600])],
        )

        img = Image.new("RGB", (400, 300), color=(80, 80, 80))
        # In Gemini mode or Hybrid mode when YOLO finds no boxes
        res = detect_image_pil(img, mode="gemini", actor=self.admin_user)
        self.assertIsInstance(res, DetectionResult)
        self.assertEqual(len(res.detections), 1)
        self.assertEqual(res.detections[0].class_name, "streetlight")
        self.assertEqual(res.detections[0].source, "gemini")
        self.assertEqual(res.detections[0].confidence_source, "gemini_estimate")

    def test_scoring_with_gemini_estimated_confidence(self):
        # Gemini detections have confidence = None
        score, label = compute_severity(area_ratio=0.08, confidence=None, detect_count=1)
        self.assertIsInstance(score, float)
        self.assertIn(label, ["Low", "Medium", "High"])

        bk = severity_breakdown(0.08, None, 1, "hospital", 1)
        self.assertTrue(bk["is_confidence_estimated"])
        self.assertIn("Estimated confidence (Gemini)", [c["name"] for c in bk["components"]])

    @patch("core.gemini_client.get_client")
    def test_assistant_query_parser(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "hazard_types": ["pothole"],
            "severities": ["High"],
            "statuses": ["reported"],
            "area": "Vijay Nagar",
            "assigned_to": "unassigned",
            "near_location_type": "school",
            "days_back": 7,
            "explanation": "Extracted unassigned high severity potholes in Vijay Nagar near schools for the last week.",
        })
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        parsed = _parse_query_with_gemini("show me unassigned high potholes near schools in Vijay Nagar this week", self.admin_user)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hazard_types, ["pothole"])
        self.assertEqual(parsed.severities, ["High"])
        self.assertEqual(parsed.near_location_type, "school")
        self.assertEqual(parsed.days_back, 7)

    @patch("core.gemini_client.get_client")
    def test_weekly_brief_generation(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "title": "Municipal Infrastructure Operations Weekly Report",
            "executive_summary": "During the reporting period, 32 total infrastructure incidents were tracked.",
            "key_takeaways": ["12 high severity potholes require immediate patching.", "85% resolution rate achieved in Palasia."],
            "action_items": ["Deploy cold-mix patch team to Vijay Nagar.", "Clear drainage blockages before weekend rain."],
        })
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        stats = {"total_issues_in_period": 32, "status_breakdown": {"reported": 10, "fixed": 22}}
        brief = generate_weekly_brief(stats, self.admin_user)
        self.assertIsNotNone(brief)
        self.assertIsInstance(brief, WeeklyBriefReport)
        self.assertEqual(len(brief.action_items), 2)


if __name__ == "__main__":
    unittest.main()
