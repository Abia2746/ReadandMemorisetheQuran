"""Regression tests for the Prayer Room economy (isolated, disposable SQLite)."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import prayer_room as room


class PrayerRoomTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch_db = patch.object(room, "_DB", pathlib.Path(self.tmp.name) / "test.db")
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()
        self.tmp.cleanup()

    def test_first_visit_has_starter_coins_and_no_owned_decor(self):
        state = room.get_room_state("Student")
        self.assertEqual(state["coins"], 100)
        self.assertEqual(state["xp"], 0)
        self.assertEqual(state["owned"], [])
        self.assertEqual(len(state["items"]), 21)

    def test_one_read_once_per_verse_per_utc_day(self):
        result = room.earn("Student", "read", 2, 60, today="2026-11-19")
        self.assertTrue(result["ok"])
        dup = room.earn("Student", "read", 2, 60, today="2026-11-19")
        self.assertFalse(dup["ok"])
        state = room.get_room_state("Student")
        self.assertEqual(state["xp"], 50)
        self.assertEqual(state["coins"], 125)

    def test_memorisation_reward_not_a_graded_assessment(self):
        room.earn("Student", "read", 2, 60, today="2026-11-19")
        room.earn("Student", "memorise", 2, 60, today="2026-11-19")
        state = room.get_room_state("Student")
        self.assertEqual(state["xp"], 125)
        self.assertEqual(state["coins"], 165)
        self.assertFalse(room.earn(
            "Student", "memorise", 2, 60, today="2026-11-19"
        )["ok"])

    def test_cannot_buy_insufficient_coins(self):
        result = room.buy("Student", "lantern_brass")
        self.assertFalse(result["ok"])
        self.assertEqual(room.get_room_state("Student")["coins"], 100)

    def test_purchase_equips_and_deducts_once(self):
        room.earn("Student", "read", 2, 60, today="2026-11-19")
        result = room.buy("Student", "plant_olive")
        self.assertTrue(result["ok"])
        state = room.get_room_state("Student")
        self.assertEqual(state["coins"], 15)
        self.assertEqual(state["equipped"]["plant"], "plant_olive")
        self.assertIn("plant_olive",state["owned"])
        self.assertFalse(room.buy("Student", "plant_olive")["ok"])
        self.assertEqual(room.get_room_state("Student")["coins"], 15)

    def test_unlock_requires_lifetime_xp(self):
        for day in ("2026-11-19", "2026-11-20","2026-11-21"):
            room.earn("Student", "read", 2, 60, today=day)
        self.assertFalse(room.buy("Student", "mihrab_marble")["ok"])

    def test_cannot_equip_item_without_buying(self):
        self.assertFalse(room.equip("Student", "rug_emerald")["ok"])
        self.assertFalse(room.unequip("Student", "unknown")["ok"])

    def test_remove_does_not_destroy_owned_item(self):
        room.earn("Student", "read", 2, 60, today="2026-11-19")
        room.buy("Student", "plant_olive")
        self.assertTrue(room.unequip("Student", "plant")["ok"])
        state = room.get_room_state("Student")
        self.assertIn("plant_olive", state["owned"])
        self.assertIsNone(state["equipped"]["plant"])
        self.assertTrue(room.equip("Student", "plant_olive")["ok"])

    def test_review_does_not_pay_twice(self):
        h="a"*64
        first=room.earn_recording_review(
            "Student", 2, 60, 64, h, today="2026-11-19"
        )
        second=room.earn_recording_review(
            "Student", 2, 60, 64, h, today="2026-11-19"
        )
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        state=room.get_room_state("Student")
        self.assertEqual(state["xp"],100)
        self.assertEqual(state["coins"],150)

    def test_at_most_three_recording_rewards_per_day(self):
        for suffix in ("a","b","c","d"):
            room.earn_recording_review(
                "Student",2,60,64,suffix*64,today="2026-11-19"
            )
        state=room.get_room_state("Student")
        self.assertEqual(state["xp"],300)
        self.assertEqual(state["coins"],250)


if __name__ == "__main__":
    unittest.main()
