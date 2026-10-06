"""
Unit test suite for UrbanLens MapKit and geospatial features.
Covers: tile configuration, layer controls, marker styling, popup XSS safety,
backend RBAC field filtering, boundary validation, and cached geocoding.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import folium
from core.mapkit import build_map, _build_popup_html, SEV_MARKER_COLORS, STATUS_FIXED_COLOR
from core.geo import validate_coordinates, get_location_type, reverse_geocode_area
from core.db import init_db, get_map_issues, create_issue


class TestMapKit(unittest.TestCase):

    def setUp(self):
        init_db()
        self.admin_user = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        self.citizen_user = {"id": 3, "username": "citizen1", "name": "Citizen 1", "role": "citizen"}
        self.guest_user = {"id": 0, "username": "guest", "name": "Guest", "role": "guest"}

        self.sample_issues = [
            {
                "id": 101,
                "type": "pothole",
                "severity_score": 0.85,
                "severity_label": "High",
                "priority": 1.25,
                "lat": 22.7448,
                "lon": 75.9090,
                "area": "Vijay Nagar",
                "location_type": "default",
                "status": "reported",
                "report_count": 2,
                "created_at": "2026-10-06 10:00:00",
                "image_path": "",
                "reported_by": "citizen1",
                "assigned_to": "officer1",
            },
            {
                "id": 102,
                "type": "drain",
                "severity_score": 0.45,
                "severity_label": "Medium",
                "priority": 0.60,
                "lat": 22.7268,
                "lon": 75.8636,
                "area": "Palasia",
                "location_type": "school",
                "status": "fixed",
                "report_count": 1,
                "created_at": "2026-10-05 12:00:00",
                "image_path": "",
                "reported_by": "citizen2",
                "assigned_to": "officer2",
            }
        ]

    def test_severity_colors(self):
        self.assertEqual(SEV_MARKER_COLORS["High"], "#C8372D")
        self.assertEqual(SEV_MARKER_COLORS["Medium"], "#E08A1E")
        self.assertEqual(SEV_MARKER_COLORS["Low"], "#2E9E6B")
        self.assertEqual(STATUS_FIXED_COLOR, "#1B9C85")

    def test_popup_html_xss_escaping(self):
        malicious_issue = {
            "id": 999,
            "type": "<script>alert('xss')</script>",
            "severity_label": "High",
            "priority": 1.0,
            "area": "<b>Bold Area</b>",
            "status": "reported",
            "created_at": "2026-10-06 10:00:00",
        }
        popup_html = _build_popup_html(malicious_issue)
        # Verify malicious script tags are safely escaped
        self.assertNotIn("<script>", popup_html)
        self.assertIn("&lt;script&gt;", popup_html)
        self.assertIn("&lt;b&gt;Bold Area&lt;/b&gt;", popup_html)

    def test_backend_rbac_field_filtering(self):
        # Admin gets full access with reporter & assignee
        admin_map_data = get_map_issues(actor=self.admin_user)
        self.assertTrue(len(admin_map_data) > 0)
        # Guest receives sanitized records with redacted sensitive fields
        guest_map_data = get_map_issues(actor=self.guest_user)
        self.assertTrue(len(guest_map_data) > 0)
        for row in guest_map_data:
            self.assertIsNone(row["reported_by"])
            self.assertIsNone(row["assigned_to"])

    def test_coordinate_validation(self):
        # Valid Indore coordinates
        self.assertTrue(validate_coordinates(22.7196, 75.8577))
        # Invalid coordinate ranges
        self.assertFalse(validate_coordinates(95.0, 75.8577))
        self.assertFalse(validate_coordinates(22.7196, 195.0))
        self.assertFalse(validate_coordinates(None, 75.0))

    def test_build_map_renders_valid_folium_object(self):
        m = build_map(
            issues=self.sample_issues,
            cluster=False,
            show_heatmap=True,
            show_fixed=True,
            enable_satellite=True,
        )
        self.assertIsInstance(m, folium.Map)
        # Render HTML string
        rendered = m.get_root().render()
        self.assertIn("CARTO", rendered)
        self.assertIn("OpenStreetMap", rendered)
        self.assertIn("Map Legend", rendered)

    @patch("core.geo._get_cached_area")
    def test_reverse_geocode_cache(self, mock_cached):
        mock_cached.return_value = "Vijay Nagar Sector A"
        # Should return cached area immediately
        area = reverse_geocode_area(22.7450, 75.9080)
        self.assertEqual(area, "Vijay Nagar Sector A")


if __name__ == "__main__":
    unittest.main()
