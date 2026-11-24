"""Hifdh plan regression checks: persistence, changing goals and Calendar alarms."""
import datetime as dt
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import hifdh_planner as planner


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(planner,"_DB",pathlib.Path(self.tmp.name)/"hifdh.sqlite")
        self.date = patch.object(planner,"today_local",
                                 return_value=dt.date(2026,11,19))
        self.db.start()
        self.date.start()

    def tearDown(self):
        self.date.stop()
        self.db.stop()
        self.tmp.cleanup()

    def save(self, **overrides):
        settings={
            "goal":"surah","surah":112,"months":3,
            "weekdays":[0,1,2,3,4,5,6],"minutes":20,
            "review_minutes":10,"time":"18:45","remind_before":15,"focus":False
        }
        settings.update(overrides)
        return planner.save_plan("A learning profile",settings)

    def test_counts_are_complete(self):
        self.assertEqual(len(planner.SURAHS),114)
        self.assertEqual(len(planner.AYAHS),115)
        self.assertEqual(sum(planner.AYAHS),6236)

    def test_default_plan_is_not_automatically_saved(self):
        data=planner.get_state("A learning profile")
        self.assertFalse(data["configured"])
        self.assertEqual(data["goal_total"],286)
        self.assertFalse(data["finished_today"])

    def test_selected_surah_completion_is_once_per_day(self):
        self.save()
        before=planner.get_state("A learning profile")
        self.assertTrue(before["configured"])
        self.assertEqual(before["goal_total"],4)
        self.assertEqual(before["recommended_ayahs"],1)
        done=planner.finish_today("A learning profile")
        self.assertTrue(done["ok"])
        self.assertEqual(planner.get_state("A learning profile")["done"],1)
        self.assertTrue(planner.get_state("A learning profile")["finished_today"])
        self.assertFalse(planner.finish_today("A learning profile")["ok"])

    def test_revision_uses_only_prior_self_reported_verses_in_goal(self):
        self.save()
        with planner._connection() as con:
            con.executemany("INSERT INTO hifdh_completed VALUES(?,?,?,?)", [
                ("A learning profile",112,1,"2026-11-01"),
                ("A learning profile",112,2,"2026-11-18"),
                ("A learning profile",112,3,"2026-11-19"),
                ("Someone else",112,4,"2026-11-15"),
            ])
        state=planner.get_state("A learning profile")
        self.assertEqual([r["from"] for r in state["sabqi_ranges"]],[2])
        self.assertEqual([r["from"] for r in state["manzil_ranges"]],[1])
        self.save(review_minutes=0)
        self.assertFalse(planner.get_state("A learning profile")["sabqi_ranges"])

    def test_editing_plan_keeps_completed_ayahs(self):
        self.save()
        planner.finish_today("A learning profile")
        planner.save_plan("A learning profile",{
            "goal":"surah","surah":112,"months":12,
            "weekdays":[0,2,4],"minutes":35,"review_minutes":15,
            "time":"17:30","remind_before":5,"focus":True
        })
        current=planner.get_state("A learning profile")
        self.assertEqual(current["done"],1)
        self.assertEqual(current["config"]["time"],"17:30")
        self.assertTrue(current["config"]["focus"])

    def test_whole_quran_target_24_months(self):
        self.save(goal="whole",surah=2,months=24,weekdays=[0,1,2,3,4])
        plan=planner.get_state("A learning profile")
        self.assertEqual(plan["goal_total"],6236)
        self.assertEqual(plan["deadline"],"2028-11-19")
        self.assertGreater(plan["required_ayahs_per_day"],9)
        self.assertLess(plan["required_ayahs_per_day"],24)

    def test_missed_days_raise_daily_estimate(self):
        self.save(goal="whole",months=24)
        today=planner.get_state("A learning profile",day=dt.date(2026,11,19))
        later=planner.get_state("A learning profile",day=dt.date(2027,7,19))
        self.assertGreater(later["required_ayahs_per_day"],
                           today["required_ayahs_per_day"])

    def test_short_deadline_is_flagged(self):
        self.save(goal="whole",months=1)
        state=planner.get_state("A learning profile")
        self.assertTrue(state["overload"])
        self.assertLessEqual(state["recommended_ayahs"],30)

    def test_rejects_invalid_or_pressure_heavy_settings(self):
        with self.assertRaises(ValueError):
            self.save(weekdays=[])
        with self.assertRaises(ValueError):
            self.save(minutes=200)
        with self.assertRaises(ValueError):
            self.save(goal="whole",months=0)
        with self.assertRaises(ValueError):
            self.save(time="29:59")

    def test_calendar_alarms_do_not_expose_name(self):
        self.save()
        ics=planner.build_calendar("A learning profile",horizon_days=14)
        self.assertIn("BEGIN:VCALENDAR",ics)
        self.assertIn("TZID=Europe/London",ics)
        self.assertIn("BEGIN:VALARM",ics)
        self.assertIn("TRIGGER:-PT15M",ics)
        self.assertIn("END:VCALENDAR",ics)
        self.assertNotIn("A learning profile",ics)

    def test_rest_day_is_honoured(self):
        self.save(weekdays=[0,1,2,4])
        state=planner.get_state("A learning profile")
        self.assertFalse(state["study_today"])
        self.assertEqual(state["recommended_ayahs"],0)
        self.assertFalse(planner.finish_today("A learning profile")["ok"])


if __name__=="__main__":
    unittest.main()
