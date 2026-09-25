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
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", side_effect=[self._llm_predict_call(), self._llm_final()]), \
             patch.object(agent, "run_tool", return_value=fake_out) as rt:
            out = agent.run_agent([{"role": "user", "content": "Predict Bijnor please"}])
        self.assertTrue(out["llm_used"])
        self.assertEqual(out["reply"], "Bijnor looks EXTREME.")
        self.assertEqual(len(out["charts"]), 1)
        rt.assert_called_once()
        self.assertEqual(rt.call_args[0][0], "predict_district")

    def test_llm_chatter_still_deploys_charts(self):
        # Model answers without tools but intent is clear -> deterministic backfill.
        kla = {"choices": [{"message": {"content": "Sure thing!", "tool_calls": []}}]}
        with patch.object(agent, "llm_configured", return_value=True), \
             patch.object(agent, "_post_chat", return_value=kla), \
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
        calls = [
            self._call("run_sql", '{"sql": "DROP TABLE gauge_state"}'),
            self._call("run_sql", '{"sql": "SELECT station_id, rp_20 FROM station_static ORDER BY rp_20 DESC LIMIT 2"}'),
            {"choices": [{"message": {"content": "Top RP stations listed.", "tool_calls": []}}]},
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


if __name__ == "__main__":
    unittest.main()
