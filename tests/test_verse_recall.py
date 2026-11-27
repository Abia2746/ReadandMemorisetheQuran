import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import hifdh_planner as planner


class VerseRecall(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.enterContext(patch.object(planner, "_DB", pathlib.Path(tmp.name) / "study.db"))
        self.day = dt.date(2026, 11, 27)

    def record(self, offset, rating):
        return planner.record_verse_recall("a", 2, 57, rating,
                                           day=self.day + dt.timedelta(days=offset))["ok"]

    def test_retries_overdue_growth_and_meaning_lapse(self):
        self.assertTrue(self.record(0, "learnt"))
        self.assertFalse(self.record(0, "learnt"))
        self.assertFalse(self.record(0, "recalled"))
        self.assertEqual(planner.verse_reviews("a")[0]["due"], "2026-11-28")
        self.assertTrue(self.record(2, "recalled"))
        self.assertFalse(self.record(2, "recalled"))
        self.assertEqual(planner.verse_reviews("a")[0]["due"], "2026-12-02")
        self.assertTrue(self.record(5, "meaning"))
        self.assertEqual(planner.verse_reviews("a")[0]["due"], "2026-12-03")
        self.assertTrue(self.record(6, "prompt"))
        self.assertEqual(planner.verse_reviews("a")[0]["due"], "2026-12-04")
        self.assertEqual(planner.verse_reviews("b"), [])

    def test_old_plan_history_and_new_unplanned_recall_roundtrip(self):
        planner.import_cloud_snapshot("a", {"completed":[
            {"surah":2,"ayah":57,"completed":"2026-11-01T18:00:00Z"}]})
        self.assertEqual(planner.verse_reviews("a")[0]["due"], "2026-11-02")
        self.assertTrue(self.record(0, "recalled"))
        snapshot = planner.export_cloud_snapshot("a")
        self.assertEqual(snapshot["plan"], {})
        planner.import_cloud_snapshot("b", snapshot)
        self.assertEqual(planner.verse_reviews("a"), planner.verse_reviews("b"))
        self.assertFalse(planner.get_state("b")["configured"])

    def test_planned_session_enters_review_without_extra_click(self):
        planner.save_plan("a", {"goal":"surah","surah":112,"weekdays":list(range(7))})
        self.assertTrue(planner.finish_today("a")["ok"])
        self.assertEqual(planner.verse_reviews("a")[0]["surah"], 112)
        self.assertEqual(planner.verse_reviews("a")[0]["due"],
                         (planner.today_local()+dt.timedelta(days=1)).isoformat())
