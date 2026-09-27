"""Phase 07-prediction-backfill-guarantee: anchor->today is always computed
with per-date live dynamic features, on both prediction entry points.

Uses in-memory fakes (no live HTTP, no torch model, no real DB file).
"""
import os as _os
import sys as _sys

_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

import database
import prediction_service as ps


ANCHOR = date(2026, 9, 22)
TODAY = date(2026, 9, 27)


class FakeDB:
    """In-memory stand-in for the database module functions in use."""

    def __init__(self):
        self.gauge = {}  # (sid, date_str) -> flow
        self.rain = {}   # (sid, date_str) -> mm

    # -- database API surface used by prediction_service --
    def get_station(self, station_id):
        if station_id != 0:
            return None
        return {"station_id": 0, "station_name": "Test Gauge",
                "latitude": 29.0, "longitude": 78.0}

    def get_rainfall_history(self, station_id):
        return [{"date": d, "rainfall_mm": m}
                for (s, d), m in sorted(self.rain.items()) if s == station_id]

    def get_gauge_state(self, station_id, limit=2, before_date=None):
        rows = [{"date": d, "raw_streamflow": f}
                for (s, d), f in self.gauge.items()
                if s == station_id and (before_date is None or d < before_date)]
        rows.sort(key=lambda r: r["date"], reverse=True)
        return rows[:limit]

    def get_rainfall_for_date(self, station_id, date_str):
        return self.rain.get((station_id, date_str))

    def insert_rainfall(self, station_id, date_str, rainfall_mm):
        self.rain.setdefault((station_id, date_str), float(rainfall_mm))

    def insert_gauge_state(self, station_id, date_str, raw_streamflow, source=None):
        self.gauge[(station_id, date_str)] = float(raw_streamflow)

    def query_one(self, sql, params=None):
        if params and len(params) == 2:
            sid, d = params
            if (sid, d) in self.gauge:
                return {"raw_streamflow": self.gauge[(sid, d)]}
        return None


class StubPredictor:
    """Deterministic model double: each step adds +10, records chain inputs."""

    def __init__(self):
        self.prevs = []

    def predict(self, x_dynamic, x_flat, prev_raw):
        self.prevs.append(float(prev_raw))
        return {"pred_raw_streamflow": float(prev_raw) + 10.0}


class BackfillGuaranteeTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDB()
        self.fake.gauge[(0, "2026-09-22")] = 100.0
        self.fake.rain[(0, "2026-09-22")] = 2.0
        self.stub = StubPredictor()
        self.live_calls = []

        def fake_live(lat, lon, date_str):
            self.live_calls.append(date_str)
            return 5.0

        def fake_window(station, rain_series, last_raw, prev_raw, target_date):
            BackfillGuaranteeTest.window_calls.append(target_date.isoformat())
            return pd.DataFrame([{"a": 1.0}])

        BackfillGuaranteeTest.window_calls = []

        self._patches = [
            patch.object(database, "get_station", self.fake.get_station),
            patch.object(database, "get_rainfall_history", self.fake.get_rainfall_history),
            patch.object(database, "get_gauge_state", self.fake.get_gauge_state),
            patch.object(database, "get_rainfall_for_date", self.fake.get_rainfall_for_date),
            patch.object(database, "insert_rainfall", self.fake.insert_rainfall),
            patch.object(database, "insert_gauge_state", self.fake.insert_gauge_state),
            patch.object(database, "query_one", self.fake.query_one),
            patch.object(ps, "_today_ist", lambda: TODAY),
            patch.object(ps, "_fetch_live_rainfall_or_raise", fake_live),
            patch.object(ps, "get_predictor", lambda: self.stub),
            patch.object(ps, "build_feature_window", fake_window),
            patch.object(ps, "preprocess_window",
                         lambda df, p: (np.zeros((15, 32), dtype=np.float32),
                                        np.zeros((42,), dtype=np.float32))),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def test_run_prediction_fills_gap_before_target(self):
        out = ps.run_prediction_for_station(0, date(2026, 9, 29))
        # Gap 09-23..09-27 persisted BEFORE extension 09-28/29.
        for d in ["2026-09-23", "2026-09-24", "2026-09-25",
                  "2026-09-26", "2026-09-27", "2026-09-28", "2026-09-29"]:
            self.assertIn((0, d), self.fake.gauge, f"missing persisted row {d}")
        # Chained: 100 -> 110 -> ... -> 170.
        self.assertEqual(self.fake.gauge[(0, "2026-09-29")], 170.0)
        self.assertEqual(out["pred_raw_streamflow"], 170.0)
        # Per-date live rainfall + window for every computed date (not one batch),
        # plus one final window rebuild for debug_features on the target.
        self.assertEqual(self.live_calls,
                         ["2026-09-23", "2026-09-24", "2026-09-25",
                          "2026-09-26", "2026-09-27", "2026-09-28", "2026-09-29"])
        self.assertEqual(BackfillGuaranteeTest.window_calls, self.live_calls + ["2026-09-29"])
        # Chain inputs carried forward.
        self.assertEqual(self.stub.prevs,
                         [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0])
        # Provenance: only the anchor->today gap is reported as backfilled.
        self.assertEqual(out["backfilled_dates"],
                         ["2026-09-23", "2026-09-24", "2026-09-25",
                          "2026-09-26", "2026-09-27"])
        self.assertTrue(all(a["rainfall_source"] == "live" for a in out["backfilled"]))

    def test_predict_future_past_target_answered_from_backfill(self):
        out = ps.predict_future_streamflow(0, date(2026, 9, 25))
        # Full gap still computed even though target < today.
        for d in ["2026-09-23", "2026-09-24", "2026-09-25",
                  "2026-09-26", "2026-09-27"]:
            self.assertIn((0, d), self.fake.gauge, f"missing gap row {d}")
        # Target answered, never an empty success.
        self.assertEqual(out["pred_raw_streamflow"], 130.0)
        self.assertEqual(out["anchor_streamflow"], 120.0)
        self.assertEqual(out["pred_delta_raw"], 10.0)
        self.assertEqual(out["trajectory"], [])
        self.assertEqual(out["backfilled_dates"],
                         ["2026-09-23", "2026-09-24", "2026-09-25",
                          "2026-09-26", "2026-09-27"])

    def test_predict_future_future_target_covers_gap_then_trajectory(self):
        out = ps.predict_future_streamflow(0, date(2026, 9, 29), source="forecast")
        self.assertEqual([t["date"] for t in out["trajectory"]],
                         ["2026-09-28", "2026-09-29"])
        self.assertEqual(out["trajectory"][0]["anchor_streamflow"], 150.0)
        self.assertEqual(out["pred_raw_streamflow"], 170.0)
        self.assertEqual(len(out["backfilled_dates"]), 5)

    def test_live_429_breaker_falls_back_with_provenance(self):
        calls = []

        def flaky(lat, lon, date_str):
            calls.append(date_str)
            raise Exception("429 Too Many Requests")

        with patch.object(ps, "_fetch_live_rainfall_or_raise", flaky), \
             patch.object(ps, "fetch_rainfall_batch", return_value={}) as batch:
            out = ps.run_prediction_for_station(0, date(2026, 9, 24))
        # One live attempt, then the breaker stops hammering; one lazy batch.
        self.assertEqual(calls, ["2026-09-23"])
        self.assertEqual(batch.call_count, 1)
        by_date = {a["date"]: a for a in out["backfilled"]}
        self.assertEqual(by_date["2026-09-23"]["rainfall_source"], "fallback-zero")
        self.assertEqual(by_date["2026-09-24"]["rainfall_source"], "fallback-zero")
        # Flow still computed (+10 chain) despite missing rainfall.
        self.assertEqual(self.fake.gauge[(0, "2026-09-24")], 120.0)

    def test_existing_rows_never_rewritten(self):
        # A stored row on 09-23 moves the anchor to 09-23. Target 09-24 is in
        # the past, so the full gap anchor->today (09-24..09-27) is still filled.
        self.fake.gauge[(0, "2026-09-23")] = 999.0
        self.fake.rain[(0, "2026-09-23")] = 7.0
        out = ps.run_prediction_for_station(0, date(2026, 9, 24))
        self.assertEqual(self.fake.gauge[(0, "2026-09-23")], 999.0)
        self.assertEqual([a["date"] for a in out["backfilled"]],
                         ["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"])
        # Stored value advances the chain (999 -> 1009 -> ...).
        self.assertEqual(self.stub.prevs, [999.0, 1009.0, 1019.0, 1029.0])
        self.assertEqual(out["pred_raw_streamflow"], 1009.0)
        self.assertEqual(self.fake.gauge[(0, "2026-09-27")], 1039.0)

    def test_future_row_reused_not_recomputed(self):
        # Unit: _step_single_date on a date with a stored row reuses it —
        # chain passes the stored value through, no live call, no window build.
        from datetime import date as _date
        self.fake.gauge[(0, "2026-09-28")] = 555.0
        self.fake.rain[(0, "2026-09-28")] = 7.0
        import pandas as _pd
        series = _pd.Series(
            [r["rainfall_mm"] for r in self.fake.get_rainfall_history(0)],
            index=_pd.to_datetime([r["date"] for r in self.fake.get_rainfall_history(0)]))
        audit, new_last, new_prev = ps._step_single_date(
            self.fake.get_station(0), series, _date(2026, 9, 28),
            150.0, 140.0, None, {"cache": None}, "forecast")
        self.assertFalse(audit["computed"])
        self.assertEqual(audit["rainfall_source"], "db")
        self.assertEqual((new_last, new_prev), (555.0, 150.0))
        self.assertEqual(self.live_calls, [])
        self.assertEqual(BackfillGuaranteeTest.window_calls, [])
        self.assertEqual(self.stub.prevs, [])

    def test_anchor_at_future_row_extends_from_it(self):
        # A stored future row (earlier forecast) becomes the anchor: the gap
        # is empty and the trajectory extends from the stored value.
        self.fake.gauge[(0, "2026-09-28")] = 555.0
        self.fake.rain[(0, "2026-09-28")] = 7.0
        out = ps.predict_future_streamflow(0, date(2026, 9, 29), source="forecast")
        self.assertEqual(self.fake.gauge[(0, "2026-09-28")], 555.0)
        self.assertEqual(out["backfilled_dates"], [])
        self.assertEqual([t["date"] for t in out["trajectory"]], ["2026-09-29"])
        self.assertEqual(out["trajectory"][0]["anchor_streamflow"], 555.0)
        self.assertEqual(out["trajectory"][0]["pred_raw_streamflow"], 565.0)
        self.assertEqual(self.stub.prevs, [555.0])

    def test_client_rainfall_shortcircuits_live_per_date(self):
        out = ps.run_prediction_for_station(
            0, date(2026, 9, 24), client_rainfall={"2026-09-23": 12.5})
        by_date = {a["date"]: a for a in out["backfilled"]}
        self.assertEqual(by_date["2026-09-23"]["rainfall_source"], "client")
        self.assertEqual(by_date["2026-09-23"]["rainfall_mm"], 12.5)
        self.assertNotIn("2026-09-23", self.live_calls)
        self.assertIn("2026-09-24", self.live_calls)

    def test_empty_gap_is_noop(self):
        for i, d in enumerate(["2026-09-23", "2026-09-24", "2026-09-25",
                               "2026-09-26", "2026-09-27"]):
            self.fake.gauge[(0, d)] = 110.0 + 10 * i
        out = ps.run_prediction_for_station(0, date(2026, 9, 29))
        self.assertEqual(out["backfilled_dates"], [])
        self.assertEqual(self.live_calls, ["2026-09-28", "2026-09-29"])


class AgentTargetPassthroughTest(unittest.TestCase):
    """Explicit in-window target dates must reach the model unchanged (R5)."""

    def test_in_window_explicit_target_verbatim(self):
        from chat_agent import tools
        rows = tools._db().query(
            "SELECT date FROM gauge_state WHERE station_id = ? ORDER BY date DESC LIMIT 1",
            [0])
        if not rows:
            self.skipTest("station 0 has no gauge_state rows in dev DB")
        from datetime import date as _date, timedelta as _td
        anchor = _date.fromisoformat(rows[0]["date"])
        explicit = (anchor + _td(days=3)).isoformat()
        got_anchor, got_target, fallback = tools._anchor_and_target(0, 7, explicit)
        self.assertFalse(fallback)
        self.assertEqual(got_target.isoformat(), explicit)

    def test_out_of_window_falls_back(self):
        from chat_agent import tools
        rows = tools._db().query(
            "SELECT date FROM gauge_state WHERE station_id = ? ORDER BY date DESC LIMIT 1",
            [0])
        if not rows:
            self.skipTest("station 0 has no gauge_state rows in dev DB")
        from datetime import date as _date, timedelta as _td
        anchor = _date.fromisoformat(rows[0]["date"])
        explicit = (anchor + _td(days=40)).isoformat()
        _, _, fallback = tools._anchor_and_target(0, 7, explicit)
        self.assertTrue(fallback)


if __name__ == "__main__":
    unittest.main()
