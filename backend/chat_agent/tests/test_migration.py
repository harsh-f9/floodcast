import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import sqlite3
import unittest
from unittest.mock import patch

import importlib.util as _ilu


def _load_m03():
    path = _os.path.join(_BACKEND, "Flood_prediction", "migrations", "003_station_district.py")
    spec = _ilu.spec_from_file_location("m003_station_district", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m03 = _load_m03()


class TestMigration003(unittest.TestCase):
    def _memdb(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE station_static (station_id INTEGER PRIMARY KEY, "
            "station_name TEXT NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO station_static VALUES (?, ?)",
            [(92, "hybas_4120864240"), (0, "hybas_4120789590")],
        )
        return conn

    def test_backfill_and_idempotency(self):
        conn = self._memdb()
        m03.migrate(conn)
        m03.migrate(conn)  # second run must be a stable no-op
        rows = dict(conn.execute("SELECT station_id, district FROM station_district").fetchall())
        self.assertEqual(rows[92], "Agra")
        self.assertTrue(rows[0])
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM station_district").fetchone()[0], 2)
        self.assertIn((3,), conn.execute("SELECT version FROM schema_migrations").fetchall())
        conn.close()

    def test_missing_json_records_nothing_and_retries(self):
        conn = self._memdb()
        with patch.object(m03, "_mapping_path", return_value=None):
            m03.migrate(conn)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM station_district").fetchone()[0], 0)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 3").fetchone()[0], 0)
        # Retry once JSON is available: backfills and records.
        m03.migrate(conn)
        rows = dict(conn.execute("SELECT station_id, district FROM station_district").fetchall())
        self.assertEqual(rows[92], "Agra")
        self.assertIn((3,), conn.execute("SELECT version FROM schema_migrations").fetchall())
        conn.close()

    def test_no_station_static_records_nothing(self):
        conn = sqlite3.connect(":memory:")
        m03.migrate(conn)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 3").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
