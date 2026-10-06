"""
Integration test suite for UrbanLens core modules.
"""
from __future__ import annotations

import os
import unittest
from PIL import Image

from core.auth import hash_password, check_password
from core.db import (
    init_db, create_user, has_permission,
    create_issue, get_issue, list_issues, update_issue_status,
    add_comment, get_comments, get_audit_log,
    get_issue_audit, kpi_counts
)
from core.score import compute_severity, compute_priority, severity_breakdown
from core.geo import haversine, get_location_type
from core.dedupe import find_duplicate, merge_into
from core.detect import detect_image_pil, DetectionResult


class TestUrbanLensCore(unittest.TestCase):
    def setUp(self):
        init_db()
        self.admin_user = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        self.officer_user = {"id": 2, "username": "officer1", "name": "Officer 1", "role": "officer"}
        self.citizen_user = {"id": 3, "username": "citizen1", "name": "Citizen 1", "role": "citizen"}
        self.guest_user = {"id": 0, "username": "guest", "name": "Guest", "role": "guest"}

    def test_auth_hashing(self):
        pwd = "secure_password_123"
        hashed = hash_password(pwd)
        self.assertTrue(check_password(pwd, hashed))
        self.assertFalse(check_password("wrong_password", hashed))

    def test_rbac_permissions(self):
        self.assertTrue(has_permission(self.admin_user, "view_audit"))
        self.assertFalse(has_permission(self.officer_user, "view_audit"))
        self.assertFalse(has_permission(self.citizen_user, "assign_status"))
        self.assertTrue(has_permission(self.citizen_user, "upload_report"))
        self.assertFalse(has_permission(self.guest_user, "upload_report"))

    def test_db_enforcement(self):
        # Guest trying to update status / assign should raise PermissionError
        with self.assertRaises(PermissionError):
            update_issue_status(self.guest_user, 1, "Assigned", assigned_to="officer1")

    def test_scoring_logic(self):
        score, label = compute_severity(area_ratio=0.01, confidence=0.8, detect_count=1)
        self.assertIsInstance(score, float)
        self.assertIn(label, ["Low", "Medium", "High"])

        score_high, label_high = compute_severity(area_ratio=0.5, confidence=0.95, detect_count=3)
        self.assertEqual(label_high, "High")

        # Priority calculation with hospital location multiplier (1.5)
        prio = compute_priority(severity_score=0.8, location_type="hospital", report_count=1)
        self.assertAlmostEqual(prio, 0.8 * 1.5, places=2)

        # Severity breakdown
        bk = severity_breakdown(0.1, 0.9, 2, "school", 2)
        self.assertIn("components", bk)
        self.assertIn("priority", bk)

    def test_geo_distance_and_landmarks(self):
        d = haversine(22.7196, 75.8577, 22.7196, 75.8577)
        self.assertAlmostEqual(d, 0.0, places=1)

        d_real = haversine(22.7448, 75.9090, 22.7268, 75.8636)
        self.assertTrue(4000 < d_real < 7000)

        loc_type = get_location_type(22.7470, 75.9080)
        self.assertIn(loc_type, ["school", "hospital", "highway", "default"])

    def test_detection_demo_fallback(self):
        img = Image.new("RGB", (320, 240), color=(100, 100, 100))
        res = detect_image_pil(img, conf_threshold=0.25)
        self.assertIsInstance(res, DetectionResult)
        self.assertIsNotNone(res.annotated_image)

    def test_dedupe_merge(self):
        import random
        loc_lat = 22.8000 + random.random() * 0.05
        loc_lon = 75.8000 + random.random() * 0.05
        iss_id = create_issue(
            actor=self.citizen_user,
            data={
                "type": "pothole",
                "severity_score": 0.75,
                "severity_label": "High",
                "priority": 1.12,
                "lat": loc_lat,
                "lon": loc_lon,
                "area": "Vijay Nagar",
                "location_type": "default",
                "image_path": "test_img.jpg",
                "confidence": 0.88,
            }
        )
        self.assertIsInstance(iss_id, int)

        dup_id = find_duplicate("pothole", loc_lat + 0.00002, loc_lon + 0.00002)
        self.assertIsNotNone(dup_id)
        self.assertEqual(dup_id, iss_id)

        # Merge into existing issue
        merge_into(
            duplicate_id=iss_id,
            new_image_path="test_img_2.jpg",
            confidence=0.92,
            actor=self.citizen_user,
        )
        updated_iss = get_issue(iss_id, actor=self.admin_user)
        self.assertEqual(updated_iss["report_count"], 2)


if __name__ == "__main__":
    unittest.main()
