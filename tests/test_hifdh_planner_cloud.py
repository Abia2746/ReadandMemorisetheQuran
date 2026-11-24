"""Regression tests for owner-isolated adaptive Hifdh snapshot persistence."""
import pathlib
import tempfile
import unittest

import hifdh_planner as planner


class TestCloudHifdhSnapshots(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = planner._DB
        planner._DB = pathlib.Path(self.temp_dir.name) / "planner-test.db"

    def tearDown(self):
        planner._DB = self.original_db
        self.temp_dir.cleanup()

    def test_round_trip_keeps_plan_verses_and_daily_sessions(self):
        owner = "account:owner-a"
        second = "account:owner-b"
        planner.save_plan(owner, {
            "goal": "surah", "surah": 2, "months": 24,
            "weekdays": [0,1,2,3,4,5], "minutes": 35,
            "review_minutes": 15, "time": "18:30", "remind_before": 10,
            "focus": False,
        })
        with planner._connection() as con:
            con.execute(
                "INSERT INTO hifdh_completed(name,surah,ayah,completed) "
                "VALUES(?,?,?,?)", (owner, 2, 1, "2026-11-24T12:00:00Z")
            )
            con.execute(
                "INSERT INTO hifdh_sessions(name,day,scope,surah,first_ayah,last_ayah,completed_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (owner, "2026-11-24", "0", 2, 1, 1, "2026-11-24T12:00:00Z"),
            )
        snapshot = planner.export_cloud_snapshot(owner)
        planner.import_cloud_snapshot(second, snapshot)
        self.assertEqual(planner.export_cloud_snapshot(second), snapshot)
        self.assertEqual(planner.get_state(second)["done"], 1)

    def test_bad_snapshot_does_not_erase_existing_progress(self):
        key = "account:owner-c"
        planner.save_plan(key, {"goal": "surah", "surah": 2})
        original = planner.export_cloud_snapshot(key)
        with self.assertRaises(ValueError):
            planner.import_cloud_snapshot(key, {
                "plan": {"goal": "surah", "surah": 2},
                "completed": [{"surah": 2, "ayah": 9999, "completed": "2026-11-24"}],
                "sessions": [],
            })
        self.assertEqual(planner.export_cloud_snapshot(key), original)

    def test_invalid_profiles_and_large_lists_are_rejected(self):
        with self.assertRaises(ValueError):
            planner.import_cloud_snapshot("", {})
        with self.assertRaises(ValueError):
            planner.import_cloud_snapshot("account:x", {
                "plan": {}, "completed": [], "sessions": [None] * 2001
            })


if __name__ == "__main__":
    unittest.main()
