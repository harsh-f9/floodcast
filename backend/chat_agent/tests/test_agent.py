import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from unittest.mock import patch
from chat_agent import agent
from chat_agent.tools import FALLBACK_REPLY


class TestScopeGate(unittest.TestCase):
    def test_random_question_falls_back_without_llm(self):
        with patch.object(agent, "llm_configured", return_value=True):
            out = agent.run_agent([{"role": "user", "content": "Who won the cricket match?"}])
        self.assertEqual(out["reply"], FALLBACK_REPLY)
        self.assertFalse(out["llm_used"])
        self.assertEqual(out["tool_trace"], [])

    def test_greeting_gets_capabilities(self):
        out = agent.run_agent([{"role": "user", "content": "hello"}])
        self.assertIn("Predict", out["reply"])
        self.assertFalse(out["llm_used"])

    def test_in_scope_detection(self):
        self.assertTrue(agent.in_scope("Predict Bijnor flood risk"))
        self.assertTrue(agent.in_scope("history of station 5"))
        self.assertFalse(agent.in_scope("tell me a joke"))


class TestIntentParse(unittest.TestCase):
    def test_bare_district_predicts(self):
        i = agent.parse_intent("Bijnor")
        self.assertEqual(i["kind"], "predict")
        self.assertIn("Bijnor", i["districts"])

    def test_station_history(self):
        i = agent.parse_intent("show history of station 12 for past dates")
        self.assertEqual(i["kind"], "history")
        self.assertEqual(i["station_id"], 12)

    def test_info(self):
        i = agent.parse_intent("list stations in Lucknow")
        self.assertEqual(i["kind"], "info")

    def test_top_flow_sql(self):
        i = agent.parse_intent("run for all stations, top 5 highest streamflow, graphs past 3 days each")
        self.assertEqual(i["kind"], "sql_top")
        self.assertEqual(i["days"], 3)
        self.assertEqual(i["top_n"], 5)

    def test_max_rp_sql(self):
        i = agent.parse_intent("which station has highest rp")
        self.assertEqual(i["kind"], "sql_rp")

    def test_none(self):
        i = agent.parse_intent("flood")
        self.assertEqual(i["kind"], "none")


class TestDeterministicNoKeyPath(unittest.TestCase):
    def test_history_without_key(self):
        with patch.object(agent, "llm_configured", return_value=False):
            out = agent.run_agent([{"role": "user", "content": "history of station 0"}])
        self.assertFalse(out["llm_used"])
        self.assertTrue(any(t["tool"] == "station_history" and t["ok"] for t in out["tool_trace"]))
        self.assertEqual(len(out["charts"]), 1)
        self.assertIn("Station 0", out["reply"])

    def test_predict_without_key(self):
        fake = {"horizon_days": 7, "results": [{
            "district": "Bijnor", "stations_total": 3, "stations_covered": 1,
            "truncated": True, "briefing": "Bijnor: test briefing.",
            "stations": [{
                "station_id": 0, "station_name": "hybas_x", "location_name": "",
                "thresholds": {"watch": 1, "warning": 2, "danger": 3, "extreme": 4},
                "peak_flow": 5.0, "peak_date": "2026-07-20", "severity": "EXTREME",
                "chart": [
                    {"date": "2026-07-19", "streamflow": 4.0, "kind": "past"},
                    {"date": "2026-07-20", "streamflow": 5.0, "kind": "forecast"},
                ],
            }],
        }]}
        with patch.object(agent, "llm_configured", return_value=False), \
             patch.object(agent, "run_tool", return_value=fake):
            out = agent.run_agent([{"role": "user", "content": "Predict Bijnor"}])
        self.assertFalse(out["llm_used"])
        self.assertEqual(len(out["charts"]), 1)
        self.assertIn("test briefing", out["briefing"])

    def test_tool_failure_surfaces_helpfully(self):
        with patch.object(agent, "llm_configured", return_value=False), \
             patch.object(agent, "run_tool", side_effect=ValueError("Station 1 not found.")):
            out = agent.run_agent([{"role": "user", "content": "history of station 1"}])
        self.assertIn("couldn't fetch", out["reply"])

    def test_out_of_scope_never_calls_tools(self):
        with patch.object(agent, "run_tool", side_effect=AssertionError("must not run")):
            out = agent.run_agent([{"role": "user", "content": "write me a poem"}])
        self.assertEqual(out["reply"], FALLBACK_REPLY)


class TestLLMPath(unittest.TestCase):
    def _llm_predict_call(self):
        return {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {
                            "name": "predict_district",
                            "arguments": '{"districts": ["Bijnor"]}',
                        },
                    }],
                },
            }],
        }

    def _llm_final(self):
        return {"choices": [{"message": {"content": "Bijnor looks EXTREME.", "tool_calls": []}}]}

    def test_llm_tool_roundtrip(self):
        fake_out = {"horizon_days": 7, "results": [{
            "district": "Bijnor", "stations_total": 1, "stations_covered": 1,
            "truncated": False, "briefing": "Bijnor briefing.",
            "stations": [{
                "station_id": 0, "station_name": "hybas_x", "location_name": "",
                "thresholds": {"watch": 1, "warning": 2, "danger": 3, "extreme": 4},
                "peak_flow": 5.0, "peak_date": "2026-07-20", "severity": "EXTREME",
                "chart": [{"date": "2026-07-20", "streamflow": 5.0, "kind": "forecast"}],
            }],
        }]}
        M = agent.model_name()
        S = agent.summary_model_name()
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", side_effect=[
                 (self._llm_predict_call(), M),
                 (self._llm_final(), M),
                 ({"choices": [{"message": {
                     "content": "- **Bijnor** peak 5.0 m3/s [Chart 1]", "tool_calls": []}}]}, S),
             ]), \
             patch.object(agent, "run_tool", return_value=fake_out) as rt:
            out = agent.run_agent([{"role": "user", "content": "Predict Bijnor please"}])
        self.assertTrue(out["llm_used"])
        self.assertEqual(out["raw_reply"], "Bijnor looks EXTREME.")
        self.assertIn("[Chart 1]", out["reply"])
        self.assertTrue(out["summary_used"])
        self.assertEqual(out["model"], M)
        self.assertEqual(out["summary_model"], S)
        self.assertEqual(len(out["charts"]), 1)
        rt.assert_called_once()
        self.assertEqual(rt.call_args[0][0], "predict_district")

    def test_llm_chatter_still_deploys_charts(self):
        # Model answers without tools but intent is clear -> deterministic backfill.
        kla = {"choices": [{"message": {"content": "Sure thing!", "tool_calls": []}}]}
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", return_value=(kla, agent.model_name())), \
             patch.object(agent, "run_tool", return_value={"station_id": 0}) as rt:
            out = agent.run_agent([{"role": "user", "content": "history of station 0"}])
        self.assertTrue(out["llm_used"])
        rt.assert_called_once()
        self.assertEqual(rt.call_args[0][0], "station_history")


class TestDeterministicSQLPath(unittest.TestCase):
    def test_top5_no_key_with_graphs(self):
        with patch.object(agent, "llm_configured", return_value=False):
            out = agent.run_agent([{
                "role": "user",
                "content": "top 5 stations with highest streamflow, show graphs past 3 days each",
            }])
        self.assertFalse(out["llm_used"])
        tools_used = [t["tool"] for t in out["tool_trace"] if t["ok"]]
        self.assertIn("run_sql", tools_used)
        self.assertIn("station_history", tools_used)
        self.assertGreaterEqual(len(out["charts"]), 1)
        for c in out["charts"]:
            self.assertLessEqual(len(c["chart"]), 3)

    def test_max_rp_no_key(self):
        with patch.object(agent, "llm_configured", return_value=False):
            out = agent.run_agent([{"role": "user", "content": "which station has highest rp"}])
        self.assertFalse(out["llm_used"])
        self.assertTrue(any(t["tool"] == "run_sql" and t["ok"] for t in out["tool_trace"]))
        self.assertIn("rp_20", out["reply"])


class TestLLMSQLRepair(unittest.TestCase):
    def _call(self, name, arguments):
        return {"choices": [{"message": {
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": name, "arguments": arguments}}],
        }}]}

    def test_drop_rejected_then_repaired(self):
        from chat_agent import sql_exec
        before = sql_exec.execute_sql("SELECT COUNT(*) AS n FROM gauge_state")
        M = agent.model_name()
        calls = [
            (self._call("run_sql", '{"sql": "DROP TABLE gauge_state"}'), M),
            (self._call("run_sql", '{"sql": "SELECT station_id, rp_20 FROM station_static ORDER BY rp_20 DESC LIMIT 2"}'), M),
            ({"choices": [{"message": {"content": "Top RP stations listed.", "tool_calls": []}}]}, M),
        ]
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", side_effect=calls):
            out = agent.run_agent([{"role": "user", "content": "which stations have the highest rp"}])
        self.assertTrue(out["llm_used"])
        denied = [t for t in out["tool_trace"] if t["tool"] == "run_sql" and not t["ok"]]
        allowed = [t for t in out["tool_trace"] if t["tool"] == "run_sql" and t["ok"]]
        self.assertTrue(denied and allowed, out["tool_trace"])
        self.assertEqual(out["reply"], "Top RP stations listed.")
        after = sql_exec.execute_sql("SELECT COUNT(*) AS n FROM gauge_state")
        self.assertEqual(before["rows"], after["rows"])


class TestSummarizerLayer(unittest.TestCase):
    def _tool_call(self, sql):
        return {"choices": [{"message": {
            "content": "",
            "tool_calls": [{"id": "c1", "function": {"name": "run_sql", "arguments": f'{{"sql": "{sql}"}}'}}],
        }}]}

    def _final(self, text):
        return {"choices": [{"message": {"content": text, "tool_calls": []}}]}

    def test_summary_replaces_reply_with_citations(self):
        sql = "SELECT station_id, rp_20 FROM station_static ORDER BY rp_20 DESC LIMIT 2"
        seen = {}

        def fake_post(messages, tools, model, max_tokens):
            if tools:
                seen["tool_model"] = model
                return self._tool_call(sql), model
            seen["summary_model"] = model
            self.assertIsNone(tools)
            return self._final("- Peak **Station 150** at 30563.3 m3/s [Chart 1]\n- Severity EXTREME"), model

        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", side_effect=fake_post):
            out = agent.run_agent([{"role": "user", "content": "which stations have the highest rp"}])
        self.assertTrue(out["summary_used"])
        self.assertIn("[Chart 1]", out["reply"])
        self.assertTrue(out["raw_reply"])
        self.assertNotEqual(out["reply"], out["raw_reply"])
        self.assertEqual(seen["summary_model"], agent.summary_model_name())
        self.assertNotEqual(seen["summary_model"], seen["tool_model"])

    def test_summary_failover_keeps_raw_reply(self):
        calls = {"n": 0}

        def fake_post(messages, tools, model, max_tokens):
            calls["n"] += 1
            if tools:
                return self._final("Raw tool answer."), model
            raise RuntimeError("summary down")

        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", side_effect=fake_post), \
             patch.object(agent, "run_tool", return_value={"station_id": 0}):
            out = agent.run_agent([{"role": "user", "content": "history of station 0"}])
        self.assertFalse(out["summary_used"])
        self.assertEqual(out["reply"], "Raw tool answer.")
        self.assertEqual(out["raw_reply"], "Raw tool answer.")

    def test_no_summary_without_key(self):
        with patch.object(agent, "llm_configured", return_value=False):
            out = agent.run_agent([{"role": "user", "content": "history of station 0"}])
        self.assertFalse(out["summary_used"])
        self.assertEqual(out["summary_model"], "")

    def test_no_summary_for_refusals(self):
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat",
                          side_effect=AssertionError("no LLM call expected")):
            out = agent.run_agent([{"role": "user", "content": "tell me a joke"}])
        self.assertFalse(out["summary_used"])

    def test_empty_summary_retried_once(self):
        empty = ({"choices": [{"message": {"content": "  ", "tool_calls": []}}]}, agent.summary_model_name())
        full = ({"choices": [{"message": {"content": "Summary ok [Chart 1]", "tool_calls": []}}]},
                agent.summary_model_name())
        with patch.object(agent, "_post_chat", side_effect=[empty, full]) as post:
            text, used, _ = agent._summarize("q", "raw", [], [])
        self.assertTrue(used)
        self.assertEqual(text, "Summary ok [Chart 1]")
        self.assertEqual(post.call_count, 2)

    def test_empty_summary_twice_fails_over(self):
        empty = ({"choices": [{"message": {"content": "", "tool_calls": []}}]}, agent.summary_model_name())
        with patch.object(agent, "_post_chat", return_value=empty):
            text, used, _ = agent._summarize("q", "raw", [], [])
        self.assertFalse(used)
        self.assertEqual(text, "raw")


class TestPaidRescue(unittest.TestCase):
    def _resp(self, status, payload=None):
        import httpx
        return httpx.Response(status, json=payload or {},
                              request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))

    def _ok(self, text="hi"):
        return self._resp(200, {"choices": [{"message": {"content": text, "tool_calls": []}}]})

    def test_primary_serves_when_healthy(self):
        import time as _t
        with patch("time.sleep"), \
             patch("httpx.post", return_value=self._ok()) as post:
            data, served = agent._post_chat([{"role": "user", "content": "x"}], None,
                                            agent.model_name(), 10)
        self.assertEqual(served, agent.model_name())
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args[1]["json"]["model"], agent.model_name())

    def test_traffic_errors_switch_to_paid_rescue(self):
        import httpx
        fb = agent.fallback_model_name()
        self.assertNotEqual(fb, agent.model_name())
        with patch("time.sleep"), \
             patch("httpx.post", side_effect=[
                 self._resp(429), self._resp(503), self._ok("rescued"),
             ]) as post:
            data, served = agent._post_chat([{"role": "user", "content": "x"}], None,
                                            agent.model_name(), 10)
        self.assertEqual(served, fb)
        self.assertEqual(data["choices"][0]["message"]["content"], "rescued")
        models = [c[1]["json"]["model"] for c in post.call_args_list]
        self.assertEqual(models, [agent.model_name()] * 2 + [fb])

    def test_timeout_falls_back(self):
        import httpx
        with patch("time.sleep"), \
             patch("httpx.post", side_effect=[
                 httpx.TimeoutException("slow"),
                 httpx.TimeoutException("slow"),
                 self._ok("rescued"),
             ]):
            _, served = agent._post_chat([{"role": "user", "content": "x"}], None,
                                         agent.model_name(), 10)
        self.assertEqual(served, agent.fallback_model_name())

    def test_404_skips_dead_slug_to_rescue(self):
        with patch("time.sleep"), \
             patch("httpx.post", side_effect=[self._resp(404), self._ok("rescued")]) as post:
            _, served = agent._post_chat([{"role": "user", "content": "x"}], None,
                                         agent.model_name(), 10)
        self.assertEqual(served, agent.fallback_model_name())
        self.assertEqual(post.call_count, 2)

    def test_400_raises_without_rescue(self):
        with patch("time.sleep"), \
             patch("httpx.post", return_value=self._resp(400, {"error": {"message": "bad"}})) as post:
            with self.assertRaises(RuntimeError):
                agent._post_chat([{"role": "user", "content": "x"}], None, agent.model_name(), 10)
        self.assertEqual(post.call_count, 1)

    def test_total_outage_raises_after_both_models(self):
        with patch("time.sleep"), \
             patch("httpx.post", return_value=self._resp(503)) as post:
            with self.assertRaises(RuntimeError):
                agent._post_chat([{"role": "user", "content": "x"}], None, agent.model_name(), 10)
        self.assertEqual(post.call_count,
                         agent.PRIMARY_ATTEMPTS + agent.FALLBACK_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
