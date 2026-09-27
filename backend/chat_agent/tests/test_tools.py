import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from unittest.mock import patch
from chat_agent import agent, tools


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
    def _fake_traj(self, sid, target, source=None):
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

    def test_briefing_peak_matches_station_peak(self):
        # Regression: briefing peaked over trajectory-only while cards peaked
        # over past+future (Bijnor-212: 168.7 forecast vs 174.0 actual).
        # Both must now agree on the full-window peak.
        def low_traj(sid, target, source=None):
            return {"trajectory": [
                {"date": target.isoformat(), "anchor_streamflow": 1.0,
                 "rainfall_mm_fetched": 0.0, "pred_delta_raw": 0.5,
                 "pred_raw_streamflow": 1.5},
            ], "rain_window": []}

        with patch.object(tools, "_predict_one", side_effect=low_traj):
            out = tools.predict_district(["Hapur"], horizon_days=2)
        d = out["results"][0]
        s = d["stations"][0]
        self.assertIn(f"{s['peak_flow']:.1f}", d["briefing"])
        self.assertIn(s["peak_date"], d["briefing"])


class TestPredictStation(unittest.TestCase):
    def _fake_traj(self, sid, target, source=None):
        return {
            "trajectory": [
                {"date": target.isoformat(), "anchor_streamflow": 5.0,
                 "rainfall_mm_fetched": 0.5, "pred_delta_raw": 1.0,
                 "pred_raw_streamflow": 6.0},
            ],
            "rain_window": [],
        }

    def test_shape_has_past_and_forecast(self):
        with patch.object(tools, "_predict_one", side_effect=self._fake_traj):
            out = tools.predict_station(92, horizon_days=2)
        self.assertEqual(out["station_id"], 92)
        self.assertEqual(out["station_name"], "hybas_4120864240")
        self.assertEqual(out["district"], "Agra")
        self.assertIn("thresholds", out)
        self.assertIn("severity", out)
        kinds = {p["kind"] for p in out["chart"]}
        self.assertEqual(kinds, {"past", "forecast"})
        self.assertEqual(out["horizon_days"], 2)

    def test_horizon_clamped(self):
        with patch.object(tools, "_predict_one", side_effect=self._fake_traj):
            out = tools.predict_station(92, horizon_days=99)
        self.assertEqual(out["horizon_days"], tools.MAX_HORIZON_DAYS)

    def test_unknown_station_raises(self):
        with self.assertRaises(ValueError):
            tools.predict_station(999999)

    def test_charts_prefer_sql_district(self):
        rows = [
            {"station_id": 92, "date": "2026-09-22", "raw_streamflow": 777.1, "district": "Agra"},
            {"station_id": 92, "date": "2026-09-21", "raw_streamflow": 700.0, "district": "Agra"},
        ]
        cards = tools.charts_from_rows(rows, ["station_id", "date", "raw_streamflow", "district"])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["district"], "Agra")
        self.assertEqual(cards[0]["peak_flow"], 777.1)

    def test_source_tagged_on_write(self):
        seen = {}

        def fake_predict(sid, target, source=None, **k):
            seen["source"] = source
            return {"trajectory": [], "rain_window": []}

        with patch("Flood_prediction.prediction_service.predict_future_streamflow",
                   side_effect=fake_predict):
            tools._predict_one(0, tools.date.today(), source="forecast")
        self.assertEqual(seen["source"], "forecast")

    def test_insert_source_param(self):
        import Flood_prediction.database as flood_db

        flood_db.insert_gauge_state(0, "2099-01-01", 1.0, source="forecast:test")
        try:
            row = flood_db.query_one(
                "SELECT raw_streamflow, source FROM gauge_state WHERE station_id = 0 AND date = '2099-01-01'")
            self.assertEqual(row["raw_streamflow"], 1.0)
            self.assertEqual(row["source"], "forecast:test")
        finally:
            flood_db.execute("DELETE FROM gauge_state WHERE station_id = 0 AND date = '2099-01-01'")

    def test_past_target_guided_to_history(self):
        with self.assertRaises(ValueError) as cm:
            tools.predict_station(0, target_date="2026-01-01")
        self.assertIn("station_history", str(cm.exception))

    def test_station_history_excludes_forecasts(self):
        import Flood_prediction.database as flood_db

        flood_db.insert_gauge_state(0, "2099-01-02", 999.0, source="forecast:test2")
        try:
            out = tools.station_history(0, days=7)
        finally:
            flood_db.execute("DELETE FROM gauge_state WHERE station_id = 0 AND date = '2099-01-02'")
        dates = [r["date"] for r in out["history"]]
        self.assertNotIn("2099-01-02", dates)
        self.assertNotEqual(out.get("peak_flow"), 999.0)

    def test_rainfall_card_mm_no_severity(self):
        rows = [{"station_id": 5, "date": "2026-09-26", "rainfall_mm": 4.0}]
        cards = tools.charts_from_rows(rows, ["station_id", "date", "rainfall_mm"])
        self.assertEqual(cards[0]["unit"], "mm")
        self.assertEqual(cards[0]["severity"], "")
        self.assertEqual(cards[0]["thresholds"],
                         {"watch": 0, "warning": 0, "danger": 0, "extreme": 0})

    def test_bad_kwargs_explicit(self):
        with self.assertRaises(ValueError) as cm:
            tools.run_tool("station_history", {"station_id": 0, "bogus_kwarg": 1})
        self.assertIn("Bad arguments", str(cm.exception))

    def test_dispatch_casts(self):
        with patch.object(tools, "_predict_one", side_effect=self._fake_traj):
            out = tools.run_tool("predict_station", {"station_id": "92"})
        self.assertEqual(out["station_id"], 92)

    def test_target_date_honored(self):
        from datetime import timedelta

        seen = {}

        def grab(sid, target, source=None):
            seen["target"] = target.isoformat()
            return self._fake_traj(sid, target)

        anchor, _, _ = tools._anchor_and_target(92, 2)
        want = (anchor + timedelta(days=3)).isoformat()
        with patch.object(tools, "_predict_one", side_effect=grab):
            tools.predict_station(92, horizon_days=2, target_date=want)
        self.assertEqual(seen["target"], want)

    def test_target_date_out_of_range_falls_back(self):
        seen = {}

        def grab(sid, target, source=None):
            seen["target"] = target.isoformat()
            return self._fake_traj(sid, target)

        with patch.object(tools, "_predict_one", side_effect=grab):
            tools.predict_station(0, horizon_days=2, target_date="2027-06-01")
        self.assertNotEqual(seen["target"], "2027-06-01")

    def test_template_confirms_saved_rows(self):
        charts = [{
            "station_id": 92, "district": "Agra", "peak_flow": 10.0,
            "peak_date": "2026-09-24", "severity": "NORMAL",
            "chart": [
                {"date": "2026-09-22", "streamflow": 8.0, "kind": "past"},
                {"date": "2026-09-23", "streamflow": 10.0, "kind": "forecast"},
                {"date": "2026-09-24", "streamflow": 9.0, "kind": "forecast"},
            ],
        }]
        text = agent._template_reply(
            [{"tool": "predict_station", "args": {}, "ok": True, "error": ""}],
            charts, [], [])
        self.assertIn("Saved 2 forecast rows", text)
        self.assertIn("2026-09-23..2026-09-24", text)


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
        self.assertEqual(names, {"predict_district", "predict_station", "sweep_stations",
                                 "station_history", "district_rainfall", "ensure_rainfall",
                                 "district_stations", "describe_tables", "run_sql"})
        for t in tools.TOOL_SCHEMAS:
            self.assertEqual(t["type"], "function")
            self.assertIn("parameters", t["function"])


if __name__ == "__main__":
    unittest.main()
