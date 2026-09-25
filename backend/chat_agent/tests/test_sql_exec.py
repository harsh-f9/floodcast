import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest

from chat_agent import sql_exec


class TestReadOnlyLayer(unittest.TestCase):
    def test_write_statements_denied_by_guard(self):
        for q in ["INSERT INTO gauge_state VALUES (0,'2000-01-01',1.0,'x','y')",
                  "DELETE FROM gauge_state", "DROP TABLE gauge_state"]:
            out = sql_exec.execute_sql(q)
            self.assertFalse(out["ok"], q)

    def test_writes_fail_inside_sqlite_even_bypassing_guard(self):
        conn = sql_exec._ro_connect(sql_exec._db_path())
        try:
            for stmt in ["INSERT INTO gauge_state VALUES (0,'2000-01-01',1.0,'x','y')",
                         "DELETE FROM gauge_state WHERE station_id = 0",
                         "DROP TABLE gauge_state"]:
                with self.subTest(stmt=stmt[:30]):
                    with self.assertRaises(Exception) as cm:
                        conn.execute(stmt)
                    self.assertIn("readonly", str(cm.exception).lower())
        finally:
            conn.close()

    def test_db_unchanged_after_attack_attempts(self):
        before = sql_exec.execute_sql("SELECT COUNT(*) AS n FROM gauge_state")
        sql_exec.execute_sql("DELETE FROM gauge_state")
        after = sql_exec.execute_sql("SELECT COUNT(*) AS n FROM gauge_state")
        self.assertTrue(before["ok"] and after["ok"])
        self.assertEqual(before["rows"], after["rows"])

    def test_valid_read(self):
        out = sql_exec.execute_sql(
            "SELECT station_id, rp_20 FROM station_static ORDER BY rp_20 DESC LIMIT 3")
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["rows"]), 3)
        self.assertIn("rp_20", out["columns"])
        self.assertFalse(out["truncated"])

    def test_row_cap_truncation_flag(self):
        out = sql_exec.execute_sql("SELECT station_id FROM gauge_state LIMIT 100")
        self.assertTrue(out["ok"])
        self.assertLessEqual(out["row_count"], 100)


if __name__ == "__main__":
    unittest.main()
