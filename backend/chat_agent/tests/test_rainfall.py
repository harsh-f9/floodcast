import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import os
import unittest
from unittest.mock import patch

from chat_agent import agent, flags
from chat_agent import tools


class TestFlags(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_defaults_on(self):
        for k in ("CHAT_DATE_IN_PROMPT", "CHAT_DISTRICT_RAINFALL"):
            os.environ.pop(k, None)
        self.assertTrue(flags.date_in_prompt())
        self.assertTrue(flags.district_rainfall())
        self.assertTrue(flags.tool_enabled("district_rainfall"))
        self.assertTrue(flags.tool_enabled("run_sql"))

    def test_env_disables(self):
        os.environ["CHAT_DATE_IN_PROMPT"] = "0"
        os.environ["CHAT_DISTRICT_RAINFALL"] = "false"
        os.environ["CHAT_RAINFALL_BACKFILL"] = "0"
        self.assertFalse(flags.date_in_prompt())
        self.assertFalse(flags.district_rainfall())
        self.assertFalse(flags.rainfall_backfill())
        self.assertFalse(flags.tool_enabled("district_rainfall"))
        self.assertFalse(flags.tool_enabled("ensure_rainfall"))
        self.assertTrue(flags.tool_enabled("run_sql"))

    def test_active_schemas_filters(self):
        with patch.dict(os.environ, {"CHAT_DISTRICT_RAINFALL": "0"}):
            names = {t["function"]["name"] for t in flags.active_schemas(tools.TOOL_SCHEMAS)}
        self.assertNotIn("district_rainfall", names)
        self.assertIn("run_sql", names)

    def test_run_tool_rejects_disabled(self):
        with patch.dict(os.environ, {"CHAT_DISTRICT_RAINFALL": "0"}):
            with self.assertRaises(ValueError) as cm:
                tools.run_tool("district_rainfall", {"district": "Lucknow"})
        self.assertIn("disabled", str(cm.exception))


class TestDatePrompt(unittest.TestCase):
    def test_prompt_carries_today_ist(self):
        prompt = agent.build_system_prompt()
        self.assertIn(tools.today_ist().isoformat(), prompt)
        self.assertIn("Asia/Kolkata", prompt)

    def test_prompt_without_date_flag(self):
        with patch.dict(os.environ, {"CHAT_DATE_IN_PROMPT": "0"}):
            prompt = agent.build_system_prompt()
        self.assertNotIn(tools.today_ist().isoformat(), prompt)


class TestIntentRainfall(unittest.TestCase):
    def test_lucknow_rainfall_few_days(self):
        i = agent.parse_intent(
            "what has been the rainfall history of Lucknow district over past few days")
        self.assertEqual(i["kind"], "district_rainfall")
        self.assertIn("Lucknow", i["districts"])
        self.assertEqual(i["days"], 3)

    def test_predict_unaffected_by_rain_word(self):
        i = agent.parse_intent("Predict Bijnor")
        self.assertEqual(i["kind"], "predict")


class TestDistrictRainfall(unittest.TestCase):
    def test_lucknow_shape(self):
        out = tools.district_rainfall("Lucknow", days=7)
        self.assertEqual(out["district"], "Lucknow")
        self.assertEqual(out["unit"], "mm")
        self.assertLessEqual(out["days_returned"], 7)
        self.assertGreater(out["stations_total"], 0)
        self.assertIsInstance(out["stale_days"], int)
        for d in out["daily"]:
            self.assertLessEqual(d["avg_rainfall_mm"], d["max_rainfall_mm"])
            self.assertGreaterEqual(d["stations_reporting"], 1)
        card = out["chart"]
        self.assertEqual(card["station_id"], -1)
        self.assertIn("Lucknow", card["label"])
        self.assertEqual(card["unit"], "mm")

    def test_unknown_district(self):
        with self.assertRaises(ValueError):
            tools.district_rainfall("Atlantis")

    def test_e2e_no_key(self):
        fake_backfill = {"district": "Lucknow", "stations": 7, "window": {}, "inserted": 0}
        with patch.object(agent, "llm_configured", return_value=False), \
             patch.dict(tools._DISPATCH, {"ensure_rainfall": lambda **k: fake_backfill}):
            out = agent.run_agent([{
                "role": "user",
                "content": "rainfall history of Lucknow district over past few days",
            }])
        self.assertFalse(out["llm_used"])
        self.assertTrue(any(t["tool"] == "district_rainfall" and t["ok"]
                            for t in out["tool_trace"]))
        self.assertTrue(any(t["tool"] == "ensure_rainfall" and t["ok"]
                            for t in out["tool_trace"]))
        self.assertEqual(len(out["charts"]), 1)
        self.assertIn("Lucknow", out["charts"][0]["label"])
        self.assertLessEqual(len(out["charts"][0]["chart"]), 3)

    def test_stale_triggers_backfill_then_reread(self):
        calls = []
        stale = {"district": "Lucknow", "unit": "mm", "anchor": "2026-07-14",
                 "today_ist": "2026-09-26", "stale_days": 74, "days_requested": 3,
                 "days_returned": 3, "stations_total": 7, "daily": [],
                 "chart": {"station_id": -1, "district": "Lucknow", "label": "L",
                           "unit": "mm", "thresholds": {}, "chart": [],
                           "severity": "", "peak_flow": 0.0, "peak_date": ""}}
        fresh = dict(stale, stale_days=0, anchor="2026-09-26")

        def fake_district(**k):
            calls.append("read")
            return fresh if len(calls) >= 2 else stale

        def fake_backfill(**k):
            calls.append("backfill")
            return {"district": "Lucknow", "stations": 7, "window": {}, "inserted": 21}

        with patch.object(agent, "llm_configured", return_value=False), \
             patch.dict(tools._DISPATCH, {"district_rainfall": fake_district,
                                          "ensure_rainfall": fake_backfill}):
            out = agent.run_agent([{
                "role": "user",
                "content": "rainfall history of Lucknow district over past few days",
            }])
        self.assertEqual(calls, ["read", "backfill", "read"])
        self.assertTrue(all(t["ok"] for t in out["tool_trace"]))


class TestEnsureRainfall(unittest.TestCase):
    def _stub_db(self, inserts):
        class Stub:
            def query_one(self, sql, params=None):
                return {"m": "2026-09-20"}

            def query(self, sql, params=None):
                return []

            def insert_rainfall(self, sid, d, r):
                inserts.append((sid, d, r))

            def get_station(self, sid):
                return None
        return Stub()

    def _fetch(self, coords, start, end):
        return [{"station_id": c["station_id"],
                 "daily": {"time": ["2026-09-24", "2026-09-25"],
                           "precipitation_sum": [1.5, None]}} for c in coords]

    def test_inserts_only_returned_dates(self):
        inserts = []
        with patch.object(tools, "_db", return_value=self._stub_db(inserts)), \
             patch.object(tools, "_fetch_rain_multi", side_effect=self._fetch) as fetch, \
             patch.object(tools.district_map, "stations_for_district",
                          return_value=[{"station_id": 0, "latitude": 1.0, "longitude": 1.0}]):
            out = tools.ensure_rainfall(district="X", days=7)
        self.assertEqual(out["stations"], 1)
        self.assertEqual(out["inserted"], 2)  # None coerced to 0.0, still a returned date
        self.assertEqual(len(inserts), 2)
        start, end = fetch.call_args[0][1], fetch.call_args[0][2]
        self.assertLessEqual(start, end)

    def test_coords_carry_lat_lon(self):
        seen = []

        def grab(coords, start, end):
            seen.extend(coords)
            return []

        with patch.object(tools, "_db", return_value=self._stub_db([])), \
             patch.object(tools, "_fetch_rain_multi", side_effect=grab), \
             patch.object(tools.district_map, "stations_for_district",
                          return_value=[{"station_id": 5, "latitude": 27.0, "longitude": 80.0}]):
            tools.ensure_rainfall(district="X", days=3)
        self.assertEqual(seen, [{"station_id": 5, "latitude": 27.0, "longitude": 80.0}])

    def test_cap_and_validation(self):
        big = [{"station_id": i, "latitude": 1.0, "longitude": 1.0} for i in range(41)]
        with patch.object(tools, "_db", return_value=self._stub_db([])), \
             patch.object(tools.district_map, "stations_for_district", return_value=big):
            with self.assertRaises(ValueError) as cm:
                tools.ensure_rainfall(district="X")
        self.assertIn("40", str(cm.exception))
        with self.assertRaises(ValueError):
            tools.ensure_rainfall(district="Atlantis")
        with self.assertRaises(ValueError):
            tools.ensure_rainfall()

    def test_flag_off(self):
        with patch.dict("os.environ", {"CHAT_RAINFALL_BACKFILL": "0"}):
            with self.assertRaises(ValueError) as cm:
                tools.ensure_rainfall(district="Lucknow")
        self.assertIn("disabled", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
