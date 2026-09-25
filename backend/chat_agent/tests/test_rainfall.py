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
        self.assertFalse(flags.date_in_prompt())
        self.assertFalse(flags.district_rainfall())
        self.assertFalse(flags.tool_enabled("district_rainfall"))
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
        with patch.object(agent, "llm_configured", return_value=False):
            out = agent.run_agent([{
                "role": "user",
                "content": "rainfall history of Lucknow district over past few days",
            }])
        self.assertFalse(out["llm_used"])
        self.assertTrue(any(t["tool"] == "district_rainfall" and t["ok"]
                            for t in out["tool_trace"]))
        self.assertEqual(len(out["charts"]), 1)
        self.assertIn("Lucknow", out["charts"][0]["label"])
        self.assertLessEqual(len(out["charts"][0]["chart"]), 3)


if __name__ == "__main__":
    unittest.main()
