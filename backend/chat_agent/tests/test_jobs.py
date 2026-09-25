import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import time
import unittest
from unittest.mock import patch

from chat_agent import jobs
from chat_agent import tools


def _card(sid, peak):
    return {"station_id": sid, "station_name": f"hybas_{sid}", "thresholds": {},
            "peak_flow": peak, "peak_date": "2026-09-22", "severity": "NORMAL",
            "chart": []}


class TestSweep(unittest.TestCase):
    def test_resolves_districts_and_ranks(self):
        with patch.object(tools, "_forecast_one_station",
                          side_effect=lambda s, h, d="": _card(s["station_id"], float(s["station_id"]))):
            out = tools.run_tool("sweep_stations", {"districts": ["Hapur"], "horizon_days": 2})
        self.assertGreater(out["swept"], 0)
        self.assertEqual(out["failed"], [])
        peaks = [t["peak_flow"] for t in out["top"]]
        self.assertEqual(peaks, sorted(peaks, reverse=True))

    def test_all_scope_and_failure_isolation(self):
        def flaky(s, h, d=""):
            if s["station_id"] == 1:
                raise RuntimeError("model blew up")
            return _card(s["station_id"], 1.0)

        with patch.object(tools, "_forecast_one_station", side_effect=flaky):
            out = tools.run_tool("sweep_stations", {"station_ids": [0, 1, 2]})
        self.assertEqual(out["swept"], 2)
        self.assertEqual(len(out["failed"]), 1)
        self.assertEqual(out["failed"][0]["station_id"], 1)

    def test_sync_cap_for_huge_scope(self):
        with patch.object(tools, "_forecast_one_station",
                          side_effect=lambda s, h, d="": _card(s["station_id"], 1.0)):
            with self.assertRaises(ValueError) as cm:
                tools.run_tool("sweep_stations", {"all_stations": True})
        self.assertIn("40", str(cm.exception))

    def test_no_cap_inside_job(self):
        jobs._job_id.set("test-job")
        try:
            with patch.object(tools, "_forecast_one_station",
                              side_effect=lambda s, h, d="": _card(s["station_id"], 1.0)):
                out = tools.run_tool("sweep_stations", {"all_stations": True})
        finally:
            jobs._job_id.set("")
        self.assertEqual(out["swept"], 378)

    def test_unknown_district_and_station_rejected(self):
        with self.assertRaises(ValueError):
            tools.run_tool("sweep_stations", {"districts": ["Atlantis"]})
        with self.assertRaises(ValueError):
            tools.run_tool("sweep_stations", {"station_ids": [999999]})
        with self.assertRaises(ValueError):
            tools.run_tool("sweep_stations", {})

    def test_schema_lists_sweep(self):
        names = {t["function"]["name"] for t in tools.TOOL_SCHEMAS}
        self.assertIn("sweep_stations", names)


class TestJobs(unittest.TestCase):
    def _wait(self, job_id, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = jobs.get_job(job_id)
            if job and job["status"] in ("done", "failed"):
                return job
            time.sleep(0.5)
        return jobs.get_job(job_id)

    def test_submit_and_poll_lifecycle(self):
        job_id = jobs.submit([{"role": "user", "content": "hi"}])
        self.assertTrue(job_id)
        job = self._wait(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "done", job.get("error"))
        import json as _json
        result = _json.loads(job["result_json"])
        self.assertIn("Predict", result["reply"])
        self.assertEqual(job["progress_done"], 0)  # short job: no sweep progress

    def test_unknown_job(self):
        self.assertIsNone(jobs.get_job("nope-not-real"))

    def test_progress_written_by_sweep(self):
        events = []

        def fake_forecast(s, h, d=""):
            import json as _json
            jobs.set_progress("prog-job", s["station_id"] + 1, 3, "sweeping")
            return _card(s["station_id"], 1.0)

        jobs.init_table()
        conn = jobs._conn()
        try:
            conn.execute("INSERT OR REPLACE INTO chat_jobs (id, status) VALUES ('prog-job', 'running')")
            conn.commit()
        finally:
            conn.close()
        jobs._job_id.set("prog-job")
        try:
            with patch.object(tools, "_forecast_one_station", side_effect=fake_forecast):
                tools.run_tool("sweep_stations", {"station_ids": [0, 1, 2]})
        finally:
            jobs._job_id.set("")
        job = jobs.get_job("prog-job")
        self.assertEqual(job["progress_done"], 3)
        self.assertEqual(job["progress_total"], 3)


if __name__ == "__main__":
    unittest.main()
