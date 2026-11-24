"""Security regressions for Supabase email callback validation.

Pure tests extract _verify_credentials from its AST so the Streamlit UI
dependency is not needed in the lightweight GitHub Actions test runner.
"""
import ast
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "auth_callback.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
FUNC = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and
            n.name == "_verify_credentials")


class Response:
    def __init__(self, code, payload=None):
        self.status_code = code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeRequests:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return next(self.replies)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url))
        return next(self.replies)


def call_verify(responses):
    transport = FakeRequests(responses)
    fn_ast = ast.Module(body=[FUNC], type_ignores=[])
    scope = {"requests": transport}
    exec(compile(fn_ast, "auth_callback.py", "exec"), scope)
    fake_config = types.ModuleType("supabase_auth")
    fake_config._settings = lambda: ("https://example.supabase.co", "publishable")
    with patch.dict(sys.modules, {"supabase_auth": fake_config}):
        result = scope["_verify_credentials"]("a" * 50, "r" * 50)
    return result, transport.calls


class VerifyCredentialsTests(unittest.TestCase):
    def test_verified_account_accepted(self):
        account, calls = call_verify([
            Response(200, {
                "id": "user-1", "email": "example@example.com",
                "email_confirmed_at": "2026-11-24T00:00:00Z",
            })
        ])
        self.assertEqual(account["user_id"], "user-1")
        self.assertEqual(len(calls), 1)

    def test_unconfirmed_email_denied(self):
        account, calls = call_verify([
            Response(200, {"id": "user-1", "email_confirmed_at": None})
        ])
        self.assertIsNone(account)
        self.assertEqual(len(calls), 1)

    def test_refresh_rotation_reverified(self):
        account, calls = call_verify([
            Response(401),
            Response(200, {"access_token": "n" * 60, "refresh_token": "q" * 60}),
            Response(200, {"id": "user-2", "email_confirmed_at": "2026-11-24"}),
        ])
        self.assertEqual(account["access_token"], "n" * 60)
        self.assertEqual(account["refresh_token"], "q" * 60)
        self.assertEqual([method for method, _ in calls], ["GET", "POST", "GET"])

    def test_failed_refresh_denied(self):
        account, calls = call_verify([Response(401), Response(400)])
        self.assertIsNone(account)
        self.assertEqual(len(calls), 2)

    def test_no_auth_tokens_written_to_query_parameters(self):
        self.assertIn("window.history.replaceState", SOURCE)
        self.assertIn("setTriggerValue(\"tokens\"", SOURCE)
        self.assertIn("am_auth_clear_storage", SOURCE)
        self.assertNotIn("window.location.search + \"?access_token", SOURCE)


if __name__ == "__main__":
    unittest.main()
