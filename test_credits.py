"""
Unit tests for the Credits, Gamification, and Verification engine.
"""

import unittest
import os
import tempfile
import sqlite3

import core.config as config
import core.db as db
import core.credits as credits


class TestCreditsEngine(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for isolation
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.orig_db_path = config.DB_PATH
        config.DB_PATH = self.temp_db.name
        db.DB_PATH = self.temp_db.name
        db.init_db()

        # Actors
        self.admin = {"id": 1, "username": "admin", "name": "Admin User", "role": "admin"}
        self.officer = {"id": 2, "username": "officer_dave", "name": "Dave Miller", "role": "officer"}
        self.citizen = {"id": 3, "username": "citizen_jane", "name": "Jane Doe", "role": "citizen"}

        # Seed users in temp db
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, name, password_hash, role, active, show_on_leaderboard, strikes, rewards_suspended, created_at) "
                "VALUES ('admin', 'Admin User', 'hash', 'admin', 1, 1, 0, 0, '2026-01-01 00:00:00')"
            )
            conn.execute(
                "INSERT INTO users (username, name, password_hash, role, active, show_on_leaderboard, strikes, rewards_suspended, created_at) "
                "VALUES ('officer_dave', 'Dave Miller', 'hash', 'officer', 1, 1, 0, 0, '2026-01-01 00:00:00')"
            )
            conn.execute(
                "INSERT INTO users (username, name, password_hash, role, active, show_on_leaderboard, strikes, rewards_suspended, created_at) "
                "VALUES ('citizen_jane', 'Jane Doe', 'hash', 'citizen', 1, 1, 0, 0, '2026-01-01 00:00:00')"
            )

    def tearDown(self):
        config.DB_PATH = self.orig_db_path
        db.DB_PATH = self.orig_db_path
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_level_calculations(self):
        lvl1 = credits.get_user_level(0)
        self.assertEqual(lvl1["level"], 1)
        self.assertEqual(lvl1["title"], "Neighbourhood Watch")
        self.assertEqual(lvl1["progress_pct"], 0.0)

        lvl2 = credits.get_user_level(150)
        self.assertEqual(lvl2["level"], 2)
        self.assertEqual(lvl2["title"], "Civic Scout")
        self.assertTrue(lvl2["progress_pct"] > 0)

        lvl5 = credits.get_user_level(1200)
        self.assertEqual(lvl5["level"], 5)
        self.assertEqual(lvl5["title"], "Civic Legend")
        self.assertEqual(lvl5["progress_pct"], 100.0)

    def test_display_name_privacy(self):
        self.assertEqual(credits.format_display_name("Jane Doe", show_on_leaderboard=True), "Jane D.")
        self.assertEqual(credits.format_display_name("Jane Doe", show_on_leaderboard=False, is_current_user=False), "Anonymous Citizen")
        self.assertEqual(credits.format_display_name("Jane Doe", show_on_leaderboard=False, is_current_user=True), "Jane D.")

    def test_verify_and_reward_report(self):
        # Create an issue submitted by citizen_jane
        issue_id = db.create_issue(self.citizen, {
            "type": "pothole",
            "severity_score": 0.8,
            "severity_label": "High",
            "priority": 85.0,
            "lat": 18.5204,
            "lon": 73.8567,
            "area": "Shivajinagar",
        })

        # Officer verifies report
        res = credits.verify_and_reward_report(self.officer, issue_id)
        self.assertEqual(res["issue"]["verification_status"], "verified")
        self.assertEqual(res["issue"]["verified_by"], "officer_dave")

        # Check rewards: base (25) + high severity (15) + first report (50) = 90
        self.assertEqual(res["total_credits_awarded"], 90)
        self.assertIn("FIRST_STEP", res["badges_awarded"])

        # Check citizen balance
        user_jane = db.get_user("citizen_jane")
        balance = db.get_user_credits_balance(user_jane["id"])
        self.assertEqual(balance, 90)

    def test_officer_cannot_self_verify(self):
        # Create issue by officer_dave
        issue_id = db.create_issue(self.officer, {
            "type": "garbage",
            "severity_score": 0.3,
            "severity_label": "Low",
            "priority": 30.0,
        })
        with self.assertRaises(ValueError):
            credits.verify_and_reward_report(self.officer, issue_id)

    def test_rejection_requires_reason(self):
        issue_id = db.create_issue(self.citizen, {
            "type": "streetlight",
            "severity_score": 0.4,
            "severity_label": "Medium",
            "priority": 40.0,
        })
        with self.assertRaises(ValueError):
            credits.reject_and_penalize_report(self.officer, issue_id, reason="")

        res = credits.reject_and_penalize_report(self.officer, issue_id, reason="Duplicate spam submission", apply_strike=True)
        self.assertEqual(res["issue"]["verification_status"], "rejected")
        self.assertTrue(res["penalty_applied"])

        user_jane = db.get_user("citizen_jane")
        self.assertEqual(user_jane["strikes"], 1)


if __name__ == "__main__":
    unittest.main()
