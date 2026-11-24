"""Prayer Room backup regression tests: owner separation and atomic validation."""
import pathlib
import tempfile
import unittest
import prayer_room as room


class TestRoomBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = room._DB
        room._DB = pathlib.Path(self.tmp.name) / "test-room.db"

    def tearDown(self):
        room._DB = self.old
        self.tmp.cleanup()

    def test_export_import_round_trip_and_account_separation(self):
        original = "account:alice"
        recovered = "account:bob"
        room.earn(original, "read", 2, 1, today="2026-11-24")
        state = room.export_room_snapshot(original)
        room.import_room_snapshot(recovered, state)
        self.assertEqual(room.export_room_snapshot(recovered), state)
        room.earn(recovered, "read", 2, 2, today="2026-11-24")
        self.assertNotEqual(
            room.export_room_snapshot(original)["xp"],
            room.export_room_snapshot(recovered)["xp"],
        )

    def test_reject_invalid_inventory_without_overwriting(self):
        owner = "account:alice"
        before = room.export_room_snapshot(owner)
        invalid = {**before, "owned": ["unknown_decoration"]}
        with self.assertRaises(ValueError):
            room.import_room_snapshot(owner, invalid)
        self.assertEqual(room.export_room_snapshot(owner), before)

    def test_reject_guest_room_backup(self):
        with self.assertRaises(ValueError):
            room.export_room_snapshot("guest:someone")
        with self.assertRaises(ValueError):
            room.import_room_snapshot("guest:someone", {})


if __name__ == "__main__":
    unittest.main()
