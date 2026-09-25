"""003 district dimension: station_district + backfill. Idempotent, Render-safe.

One row per station (district/location_name/sub_district TEXT) backfilled from
gauge_locations_enriched.json so SQL can scope district questions with a JOIN
instead of guessing. Never drops. Guarded via PRAGMA table_info.
"""

import json
import os


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _mapping_path():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "..", "..", "gauge_locations_enriched.json"),
        os.path.join(here, "..", "..", "..", "src", "data", "gauge_locations_enriched.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS station_district(
          station_id INTEGER PRIMARY KEY,
          district TEXT NOT NULL DEFAULT '',
          location_name TEXT NOT NULL DEFAULT '',
          sub_district TEXT NOT NULL DEFAULT '',
          FOREIGN KEY (station_id) REFERENCES station_static(station_id))"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_station_district_district "
        "ON station_district(district)"
    )
    if "station_static" not in _tables(conn):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, datetime('now'))"
        )
        return
    path = _mapping_path()
    if path:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        mapping = {r.get("gauge_id"): r for r in rows if r.get("gauge_id")}
        station_rows = conn.execute(
            "SELECT station_id, station_name FROM station_static").fetchall()
        filled = 0
        for sid, gname in station_rows:
            info = mapping.get(gname, {})
            conn.execute(
                "INSERT OR REPLACE INTO station_district "
                "(station_id, district, location_name, sub_district) VALUES (?, ?, ?, ?)",
                [sid, info.get("district", "") or "",
                 info.get("location_name", "") or "",
                 info.get("sub_district", "") or ""],
            )
            if info.get("district"):
                filled += 1
        print(f"003: backfilled station_district ({filled}/{len(station_rows)} with district).")
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, datetime('now'))"
    )
