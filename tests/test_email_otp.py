"""Unit tests for Streamlit Supabase OTP verification without sending emails."""
import ast
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

SOURCE=(pathlib.Path(__file__).resolve().parents[1]/"supabase_auth.py").read_text(encoding="utf-8")
TREE=ast.parse(SOURCE)
VERIFY=next(node for node in TREE.body if isinstance(node,ast.FunctionDef)
            and node.name=="verify_email_code")

class Session(dict):
    pass

def make_verify(reply, *, confirmed=True):
    state=Session()
    streamlit=types.SimpleNamespace(session_state=state)
    calls=[]
    def post(path, data):
        calls.append((path, data))
        if isinstance(reply,Exception):raise reply
        return reply
    callback=types.ModuleType("auth_callback")
    callback._verify_credentials=lambda access,refresh: (
        {"access_token":access,"refresh_token":refresh,"email":"learner@example.com",
         "user_id":"verified-user"} if confirmed else None)
    env={"re":__import__("re"),"time":__import__("time"),"st":streamlit,
         "_post":post}
    exec(compile(ast.Module(body=[VERIFY],type_ignores=[]),
                 "supabase_auth.py","exec"),env)
    return env["verify_email_code"],state,calls,callback

class TestEmailOTP(unittest.TestCase):
    def test_success_writes_validated_identity_only(self):
        fn,state,calls,callback=make_verify({"access_token":"a"*50,"refresh_token":"r"*50})
        with patch.dict(sys.modules,{"auth_callback":callback}):
            self.assertTrue(fn("learner@example.com","123456"))
        self.assertEqual(state["am_auth"]["user_id"],"verified-user")
        self.assertEqual(calls[0][0],"verify")
        self.assertEqual(calls[0][1]["type"],"email")
        self.assertNotIn("123456",str(state))

    def test_invalid_code_never_authenticates(self):
        fn,state,_,callback=make_verify(ValueError("invalid"))
        with patch.dict(sys.modules,{"auth_callback":callback}):
            with self.assertRaises(ValueError):fn("learner@example.com","123456")
        self.assertNotIn("am_auth",state)

    def test_unconfirmed_session_denied(self):
        fn,state,_,callback=make_verify(
            {"access_token":"a"*50,"refresh_token":"r"*50},confirmed=False)
        with patch.dict(sys.modules,{"auth_callback":callback}):
            with self.assertRaises(ValueError):fn("learner@example.com","123456")
        self.assertNotIn("am_auth",state)

    def test_nonnumeric_code_rejected_without_api_call(self):
        fn,state,calls,_=make_verify({})
        with self.assertRaises(ValueError):fn("learner@example.com","bad!")
        self.assertFalse(calls)

if __name__=="__main__":
    unittest.main()
