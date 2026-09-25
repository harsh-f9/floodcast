import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from unittest.mock import patch
from chat_agent import tools


class TestStationHistory(unittest.TestCase):
    def test_returns_up_to_7_chronological_rows(self):
        out = tools.station_history(0, days=7)
        self.assertEqual(out["station_id"], 0)
        self.assertLessEqual(out["days_returned"], 7)
        dates = [r["date"] for r in out["history"]]
        self.assertEqual(dates, sorted(dates))
        for r in out["history"]:
            self.assertIn(r["severity"], ("NORMAL", "WATCH", "WARNING", "DANGER", "EXTREME", "UNKNOWN"))
            self.assertIn("rainfall_mm", r)
        self.assertEqual(len(out["chart"]), out["days_returned"])

    def test_days_capped_at_7(self):
        out = tools.station_history(0, days=99)
        self.assertLessEqual(out["days_returned"], 7)

    def test_unknown_station_raises(self):
        with self.assertRaises(ValueError):
            tools.station_history(999999)


class TestDistrictStations(unittest.TestCase):
    def test_all_stations(self):
        out = tools.district_stations()
        self.assertGreater(out["count"], 300)
        self.assertIn("thresholds", out["stations"][0])

    def test_known_district(self):
        out = tools.district_stations("Bijnor")
        self.assertEqual(out["district"], "Bijnor")
        self.assertGreater(out["count"], 0)

    def test_unknown_district_raises_helpful(self):
        with self.assertRaises(ValueError) as cm:
            tools.district_stations("Atlantis")
        self.assertIn("Unknown district", str(cm.exception))


class TestPredictDistrict(unittest.TestCase):
    def _fake_traj(self, sid, target):
        return {
            "trajectory": [
                {"date": target.isoformat(), "anchor_streamflow": 10.0,
                 "rainfall_mm_fetched": 1.0, "pred_delta_raw": 2.0,
                 "pred_raw_streamflow": 12.0},
            ],
            "rain_window": [],
        }

    def test_predict_one_district_shape(self):
        with patch.object(tools, "_predict_one", side_effect=self._fake_traj):
            out = tools.predict_district(["Bijnor"], horizon_days=2)
        self.assertEqual(out["horizon_days"], 2)
        self.assertEqual(len(out["results"]), 1)
        d = out["results"][0]
        self.assertIn("briefing", d)
        self.assertLessEqual(d["stations_covered"], tools.MAX_STATIONS_PER_DISTRICT)
        s = d["stations"][0]
        self.assertIn("chart", s)
        self.assertIn("thresholds", s)
        kinds = {p["kind"] for p in s["chart"]}
        self.assertIn("forecast", kinds)
        self.assertIn("past", kinds)

    def test_predict_one_silences_emoji_prints(self):
        # prediction_service prints emoji status lines; on Windows consoles
        # (cp1252) that raises UnicodeEncodeError. _predict_one must swallow it.
        import sys
        from datetime import date

        def noisy(sid, target):
            print("\U0001f504 Loading StreamflowPredictor...")
            return {"trajectory": [], "rain_window": []}

        real = sys.stdout
        try:
            with patch("Flood_prediction.prediction_service.predict_future_streamflow", noisy):
                out = tools._predict_one(0, date(2026, 7, 20))
        finally:
            sys.stdout = real
        self.assertEqual(out, {"trajectory": [], "rain_window": []})

    def test_too_many_districts_rejected(self):
        with self.assertRaises(ValueError):
            tools.predict_district(["Bijnor", "Lucknow", "Agra"])

    def test_unknown_district_rejected(self):
        with self.assertRaises(ValueError):
            tools.predict_district(["Atlantis"])

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            tools.predict_district([])

    def test_horizon_clamped(self):
        with patch.object(tools, "_predict_one", side_effect=self._fake_traj):
            out = tools.predict_district(["Bijnor"], horizon_days=99)
        self.assertEqual(out["horizon_days"], tools.MAX_HORIZON_DAYS)


class TestDispatcher(unittest.TestCase):
    def test_run_tool_history_casts_id(self):
        out = tools.run_tool("station_history", {"station_id": "0", "days": 3})
        self.assertEqual(out["station_id"], 0)
        self.assertLessEqual(out["days_returned"], 3)

    def test_unknown_tool(self):
        with self.assertRaises(ValueError):
            tools.run_tool("delete_database", {})

    def test_schemas_are_native_tool_format(self):
        names = {t["function"]["name"] for t in tools.TOOL_SCHEMAS}
        self.assertEqual(names, {"predict_district", "station_history", "district_stations"})
        for t in tools.TOOL_SCHEMAS:
            self.assertEqual(t["type"], "function")
            self.assertIn("parameters", t["function"])


if __name__ == "__main__":
    unittest.main()
