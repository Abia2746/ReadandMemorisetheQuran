"""Exercise the actual Streamlit component registration without a model or server."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import MagicMock, patch


class RecordingBridgeTests(unittest.TestCase):
    def test_component_is_browser_local_and_histories_are_scoped(self):
        register = MagicMock()
        state = {}
        stub = SimpleNamespace(session_state=state, components=SimpleNamespace(v2=SimpleNamespace(component=register)))
        spec = importlib.util.spec_from_file_location("bridge_test_subject", Path(__file__).resolve().parents[1] / "recording_lab.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"streamlit": stub}):
            spec.loader.exec_module(module)
            module.recording_lab(1, 1, 7)
            _, args = register.return_value.call_args
            guest = args["data"]
            self.assertEqual(guest["profile"], "browser-guest")
            self.assertEqual(sum(map(int, guest["countsCsv"].split(","))), 6236)
            state["am_auth"] = {"user_id": "learner1", "token": "private"}
            module.recording_lab(2, 57, 58)
            data = register.return_value.call_args.kwargs["data"]
            self.assertNotEqual(data["profile"], guest["profile"])
            self.assertNotIn("learner1", repr(data))
            self.assertNotIn("private", repr(data))
            self.assertEqual((data["surah"], data["first"], data["end"]), (2, 57, 58))
            self.assertIn("function microphoneConditioner", register.call_args.kwargs["js"])
