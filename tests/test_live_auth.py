"""Offline regression checks for live transcription token security and studio wiring."""
import pathlib
import unittest
from unittest.mock import Mock, patch

import live_auth

ROOT = pathlib.Path(__file__).resolve().parents[1]


class LiveAuthTests(unittest.TestCase):
    def test_single_use_token_scoped_to_transcription_model(self):
        response = Mock()
        response.ok = True
        response.json.return_value = {"name": "auth_tokens/test-session"}
        with patch.object(live_auth, "configured_api_key", return_value="private-test-key"):
            with patch.object(live_auth.requests, "post", return_value=response) as post:
                token = live_auth.issue_live_token()
        self.assertEqual(token["token"], "auth_tokens/test-session")
        self.assertEqual(token["model"], "gemini-3.5-transcribe-live")
        arguments = post.call_args
        body = arguments.kwargs["json"]
        self.assertEqual(body["uses"], 1)
        self.assertEqual(
            body["liveConnectConstraints"]["model"],
            "models/gemini-3.5-transcribe-live",
        )
        self.assertEqual(
            body["liveConnectConstraints"]["config"]["responseModalities"],
            ["TEXT"],
        )
        self.assertEqual(arguments.kwargs["headers"]["x-goog-api-key"], "private-test-key")
        self.assertNotIn("private-test-key", repr(token))

    def test_missing_key_does_not_request_token(self):
        with patch.object(live_auth, "configured_api_key", return_value=""):
            with patch.object(live_auth.requests, "post") as post:
                with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                    live_auth.issue_live_token()
                post.assert_not_called()

    def test_reject_unexpected_token(self):
        response = Mock()
        response.ok = True
        response.json.return_value = {"name": "api-key-not-ephemeral"}
        with patch.object(live_auth, "configured_api_key", return_value="example"):
            with patch.object(live_auth.requests, "post", return_value=response):
                with self.assertRaisesRegex(RuntimeError, "unexpected token"):
                    live_auth.issue_live_token()

    def test_studio_uses_pcm_stream_and_transcript_events(self):
        text = (ROOT / "studio.js").read_text(encoding="utf-8")
        for expected in (
            'floatToPcm16Base64',
            'audio/pcm;rate=16000',
            'interimInputTranscription',
            'inputTranscription',
            'component.setTriggerValue("request_cloud"',
            'Gemini Live WebSocket',
        ):
            self.assertIn(expected, text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("YOUR_API_KEY", text)


if __name__ == "__main__":
    unittest.main()
