import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest

from chat_agent.sql_guard import validate_sql


class TestAdversarialBlocked(unittest.TestCase):
    CASES = [
        "DROP TABLE gauge_state",
        "DELETE FROM gauge_state",
        "UPDATE gauge_state SET raw_streamflow = 0",
        "INSERT INTO gauge_state VALUES (1, '2000-01-01', 1.0)",
        "SELECT * FROM gauge_state; DROP TABLE gauge_state",
        "SELECT * FROM gauge_state",
        "SELECT * FROM sqlite_master",
        "SELECT station_id FROM nope",
        "SELECT bogus FROM gauge_state",
        "SELECT station_id FROM gauge_state WHERE bogus > 1",
        "SELECT load_extension('x')",
        "SELECT readfile('/etc/passwd')",
        "SELECT writefile('/tmp/x', 'y')",
        "SELECT * FROM gauge_state g UNION SELECT * FROM station_static s",
        "ATTACH DATABASE '/etc/passwd' AS p",
        "PRAGMA table_info(gauge_state)",
        "VACUUM",
        "SELECT station_id FROM gauge_state LIMIT 99999",
        "SELECT station_id FROM gauge_state LIMIT @n",
        "SELECT station_id FROM gauge_state LIMIT 10 + 10",
        "SELECT station_id FR/**/OM gauge_state",
        "",
        "   ",
    ]

    def test_all_blocked(self):
        for q in self.CASES:
            with self.subTest(sql=q[:50]):
                ok, errs, norm = validate_sql(q)
                self.assertFalse(ok, q)
                self.assertTrue(errs)
                self.assertIsNone(norm)


class TestValidAllowed(unittest.TestCase):
    CASES = [
        "SELECT station_id, date, raw_streamflow FROM gauge_state ORDER BY raw_streamflow DESC LIMIT 5",
        "WITH t AS (SELECT station_id, MAX(raw_streamflow) m FROM gauge_state GROUP BY station_id) "
        "SELECT s.station_id, s.rp_20, t.m FROM station_static s JOIN t ON t.station_id = s.station_id ORDER BY t.m DESC",
        "SELECT COUNT(*) FROM gauge_state",
        "SELECT station_id FROM gauge_state",
        "SELECT s.station_id, MAX(g.raw_streamflow) AS peak FROM station_static s "
        "JOIN gauge_state g ON g.station_id = s.station_id GROUP BY s.station_id ORDER BY peak DESC LIMIT 5",
        "SELECT station_id, rp_20 FROM station_static ORDER BY rp_20 DESC LIMIT 5",
        "SELECT AVG(rainfall_mm) AS avg_rain FROM station_rainfall_history WHERE station_id = 0",
    ]

    def test_all_allowed(self):
        for q in self.CASES:
            with self.subTest(sql=q[:50]):
                ok, errs, norm = validate_sql(q)
                self.assertTrue(ok, f"{q} -> {errs}")
                self.assertTrue(norm)

    def test_limit_injected_when_missing(self):
        ok, _, norm = validate_sql("SELECT station_id FROM gauge_state")
        self.assertTrue(ok)
        self.assertIn("LIMIT 100", norm)

    def test_comment_hidden_attack_rendered_inert(self):
        # The DROP lives inside a comment: stripping removes the attack and
        # the benign remainder runs. The attack must not survive.
        ok, errs, norm = validate_sql("SELECT station_id FROM gauge_state --; DROP TABLE gauge_state")
        self.assertTrue(ok, errs)
        self.assertNotIn("DROP", norm.upper())


if __name__ == "__main__":
    unittest.main()
