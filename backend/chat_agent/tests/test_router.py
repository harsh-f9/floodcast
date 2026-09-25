import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chat_agent import kill_switch
from chat_agent.router import router


def _app():
    app = FastAPI()
    app.include_router(router)
    return app


class TestChatRouter(unittest.TestCase):
    def setUp(self):
        kill_switch.CHAT_ENABLED = True
        self.client = TestClient(_app())

    def tearDown(self):
        kill_switch.CHAT_ENABLED = True

    def test_status_ok(self):
        r = self.client.get("/api/chat/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["enabled"])
        self.assertGreater(body["districts"], 50)

    def test_out_of_scope_returns_fallback(self):
        r = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "tell me a joke"}]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("can't answer", body["reply"])
        self.assertEqual(body["charts"], [])

    def test_history_end_to_end_no_key(self):
        with patch("chat_agent.agent.llm_configured", return_value=False):
            r = self.client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "history of station 0"}]},
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["charts"]), 1)
        self.assertTrue(body["charts"][0]["chart"])

    def test_kill_switch_503(self):
        kill_switch.CHAT_ENABLED = False
        r = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(r.status_code, 503)
        r = self.client.get("/api/chat/status")
        self.assertFalse(r.json()["enabled"])

    def test_validation_empty_messages(self):
        r = self.client.post("/api/chat", json={"messages": []})
        self.assertEqual(r.status_code, 422)

    def test_validation_bad_role(self):
        r = self.client.post("/api/chat", json={"messages": [{"role": "hacker", "content": "x"}]})
        self.assertEqual(r.status_code, 422)

    def test_internal_error_never_leaks(self):
        with patch("chat_agent.router.run_agent", side_effect=RuntimeError("boom")):
            r = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "Predict Bijnor"}]})
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("boom", r.text)


if __name__ == "__main__":
    unittest.main()
