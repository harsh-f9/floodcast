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

    def test_request_id_returned_and_logged(self):
        with patch("chat_agent.agent.llm_configured", return_value=False):
            with self.assertLogs("chat_agent", level="INFO") as cm:
                r = self.client.post(
                    "/api/chat",
                    json={"messages": [{"role": "user", "content": "history of station 0"}]},
                )
        body = r.json()
        self.assertEqual(r.status_code, 200)
        rid = body.get("request_id", "")
        self.assertTrue(rid)
        blob = "\n".join(cm.output)
        self.assertIn(rid, blob)
        self.assertIn("tool.done", blob)
        self.assertIn("chat.response", blob)

    def test_top5_end_to_end_no_key(self):
        with patch("chat_agent.agent.llm_configured", return_value=False):
            r = self.client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "top 5 stations with highest streamflow, graphs past 3 days"}]},
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertGreaterEqual(len(body["charts"]), 1)
        self.assertTrue(all(len(c["chart"]) <= 3 for c in body["charts"]))

    def test_kill_switch_503(self):
        kill_switch.CHAT_ENABLED = False
        r = self.client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(r.status_code, 503)
        r = self.client.get("/api/chat/status")
        self.assertFalse(r.json()["enabled"])

    def test_stream_endpoint_frames(self):
        import json as _json

        with patch("chat_agent.agent.llm_configured", return_value=False):
            r = self.client.post(
                "/api/chat/stream",
                json={"messages": [{"role": "user", "content": "history of station 0"}]},
            )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/event-stream", r.headers["content-type"])
        frames = []
        for chunk in r.text.split("\n\n"):
            for line in chunk.split("\n"):
                if line.startswith("data:"):
                    try:
                        frames.append(_json.loads(line[5:]))
                    except Exception:
                        pass
        kinds = [f.get("type") for f in frames]
        self.assertIn("run_started", kinds)
        self.assertIn("tool_start", kinds)
        self.assertIn("tool_end", kinds)
        self.assertIn("run_finished", kinds)
        result = next(f for f in frames if f.get("type") == "result")
        self.assertEqual(len(result["result"]["charts"]), 1)

    def test_stream_kill_switch(self):
        kill_switch.CHAT_ENABLED = False
        r = self.client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(r.status_code, 503)

    def test_stream_concurrency_cap(self):
        import chat_agent.router as _router

        _router._stream_inflight[0] = _router._STREAM_MAX
        try:
            r = self.client.post(
                "/api/chat/stream",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        finally:
            _router._stream_inflight[0] = 0
        self.assertEqual(r.status_code, 429)

    def test_job_submit_and_poll(self):
        with patch("chat_agent.agent.llm_configured", return_value=False):
            r = self.client.post(
                "/api/chat/jobs",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(r.status_code, 202)
        job_id = r.json()["job_id"]
        self.assertTrue(job_id)
        import time as _time

        body = {}
        for _ in range(30):
            pr = self.client.get(f"/api/chat/jobs/{job_id}")
            self.assertEqual(pr.status_code, 200)
            body = pr.json()
            if body["status"] in ("done", "failed"):
                break
            _time.sleep(0.5)
        self.assertEqual(body["status"], "done")
        self.assertIn("Predict", body["result"]["reply"])
        self.assertIn("events", body)
        self.assertEqual(body["progress_done"], 0)

    def test_job_unknown_404(self):
        r = self.client.get("/api/chat/jobs/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_job_cancel_endpoint(self):
        from chat_agent import jobs as _jobs

        _jobs.init_table()
        conn = _jobs._conn()
        try:
            conn.execute("INSERT OR REPLACE INTO chat_jobs (id, status) VALUES ('cancel-ep', 'queued')")
            conn.commit()
        finally:
            conn.close()
        r = self.client.delete("/api/chat/jobs/cancel-ep")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "cancelled")
        r = self.client.delete("/api/chat/jobs/does-not-exist")
        self.assertEqual(r.status_code, 404)
        conn = _jobs._conn()
        try:
            conn.execute("DELETE FROM chat_jobs WHERE id = 'cancel-ep'")
            conn.commit()
        finally:
            conn.close()

    def test_job_submit_queue_full_429(self):
        from chat_agent import jobs as _jobs

        with patch.object(_jobs, "submit", side_effect=_jobs.QueueFullError("full")):
            r = self.client.post(
                "/api/chat/jobs",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(r.status_code, 429)
        self.assertTrue(r.json()["detail"]["suggest_jobs"])

    def test_job_submit_kill_switch(self):
        kill_switch.CHAT_ENABLED = False
        r = self.client.post(
            "/api/chat/jobs",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(r.status_code, 503)

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
