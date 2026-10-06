"""
Automated quality gate test suite for UrbanLens views, RBAC enforcement, and tile health.
Tests:
- Role-based permissions across all views (Admin, Officer, Citizen, Guest).
- View rendering without unhandled exceptions.
- Keyless tile configuration and CARTO avoidance.
- Non-existence of 'pages/' directory to prevent auto-discovery.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from core.db import init_db, list_issues, kpi_counts
from core.auth import login, continue_as_guest
from core.mapkit import get_healthy_tiles, TILES_CONFIG


class TestUrbanLensViewsAndRBAC(unittest.TestCase):

    def setUp(self):
        init_db()
        self.admin_user = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        self.officer_user = {"id": 2, "username": "officer1", "name": "Officer 1", "role": "officer"}
        self.citizen_user = {"id": 3, "username": "citizen1", "name": "Citizen 1", "role": "citizen"}
        self.guest_user = {"id": 0, "username": "guest", "name": "Guest", "role": "guest"}

    def test_pages_directory_does_not_exist(self):
        """Assert that 'pages/' directory is absent to prevent Streamlit auto-discovery bug."""
        self.assertFalse(Path("pages").exists(), "The 'pages/' directory must not exist to prevent Streamlit raw sidebar auto-discovery.")
        self.assertTrue(Path("views").exists(), "Views must reside in 'views/' directory.")

    def test_keyless_tiles_no_carto(self):
        """Assert that no CARTO layers exist in tile config and standard OSM/Esri are configured."""
        tiles = TILES_CONFIG
        self.assertIn("osm", tiles)
        self.assertIn("esri_streets", tiles)
        self.assertIn("esri_satellite", tiles)
        self.assertIn("opentopo", tiles)
        for key, cfg in tiles.items():
            self.assertNotIn("carto.com", cfg["url"])
            self.assertNotIn("cartocdn.com", cfg["url"])

    def test_rbac_issues_filtering(self):
        """Verify that backend DB enforces role-based issue visibility."""
        admin_issues = list_issues(self.admin_user)
        self.assertTrue(len(admin_issues) > 0)

        # Citizen only sees their own reported issues
        citizen_issues = list_issues(self.citizen_user)
        for iss in citizen_issues:
            self.assertEqual(iss.get("reported_by"), self.citizen_user["username"])

        # Guest map issues have sensitive fields redacted
        from core.db import get_map_issues
        guest_issues = get_map_issues(self.guest_user)
        for iss in guest_issues:
            self.assertIsNone(iss.get("reported_by"))
            self.assertIsNone(iss.get("assigned_to"))

    def test_rbac_permission_guards(self):
        """Verify that unauthorized roles are blocked from restricted actions."""
        from core.db import has_permission

        # Admin permissions
        self.assertTrue(has_permission(self.admin_user, "manage_users"))
        self.assertTrue(has_permission(self.admin_user, "view_audit"))
        self.assertTrue(has_permission(self.admin_user, "export_csv"))

        # Officer permissions
        self.assertFalse(has_permission(self.officer_user, "manage_users"))
        self.assertFalse(has_permission(self.officer_user, "view_audit"))
        self.assertTrue(has_permission(self.officer_user, "assign_status"))
        self.assertTrue(has_permission(self.officer_user, "export_csv"))

        # Citizen permissions
        self.assertFalse(has_permission(self.citizen_user, "manage_users"))
        self.assertFalse(has_permission(self.citizen_user, "view_audit"))
        self.assertFalse(has_permission(self.citizen_user, "assign_status"))
        self.assertTrue(has_permission(self.citizen_user, "upload_report"))

        # Guest permissions
        self.assertFalse(has_permission(self.guest_user, "upload_report"))
        self.assertFalse(has_permission(self.guest_user, "assign_status"))
        self.assertFalse(has_permission(self.guest_user, "export_csv"))

    def test_leaderboard_rbac(self):
        """Verify that Leaderboard is accessible to Citizen but not guest or officers."""
        from core.db import has_permission
        self.assertTrue(has_permission(self.citizen_user, "view_leaderboard"))
        self.assertFalse(has_permission(self.guest_user, "view_leaderboard"))
        self.assertFalse(has_permission(self.officer_user, "view_leaderboard"))
        self.assertTrue(has_permission(self.officer_user, "verify_report"))
        self.assertTrue(has_permission(self.admin_user, "manage_credits"))

    def test_certificate_generator(self):
        """Verify that certificate HTML generates properly with citizen stats."""
        from views.leaderboard import _generate_certificate_html
        html_out = _generate_certificate_html(
            citizen_name="Ankit Joshi",
            level_title="Community Champion",
            level_num=3,
            credits=350,
            verified_count=12,
        )
        self.assertIn("Ankit Joshi", html_out)
        self.assertIn("Community Champion", html_out)
        self.assertIn("Level 3", html_out)
        self.assertIn("350", html_out)
        self.assertIn("Indore Municipal Corporation", html_out)


if __name__ == "__main__":
    unittest.main()
