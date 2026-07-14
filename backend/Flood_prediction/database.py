"""
SQLite database wrapper for the Flood Prediction system.
Manages 4 tables: station_static, station_rainfall_history, gauge_state, station_flow_percentiles.
"""

import sqlite3
import json
import os
import threading

DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "flood_prediction.db")

# Thread-local storage for connections (SQLite connections can't be shared across threads)
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_tables():
    """Create all 4 tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS station_static (
            station_id       INTEGER PRIMARY KEY,
            station_name     TEXT NOT NULL,
            latitude         REAL NOT NULL,
            longitude        REAL NOT NULL,
            UP_AREA          REAL NOT NULL DEFAULT 0.0,
            DIST_SINK        REAL NOT NULL DEFAULT 0.0,
            slp_dg           REAL NOT NULL DEFAULT 0.0,
            slp_dg_uav       REAL NOT NULL DEFAULT 0.0,
            for_pc           REAL NOT NULL DEFAULT 0.0,
            urb_pc           REAL NOT NULL DEFAULT 0.0,
            attenuation_factor        REAL NOT NULL DEFAULT 0.0,
            flow_velocity_km_per_day  REAL NOT NULL DEFAULT 0.0,
            upstream_lag1_days        REAL NOT NULL DEFAULT 0.0,
            upstream_lag2_days        REAL NOT NULL DEFAULT 0.0,
            rp_2             REAL NOT NULL DEFAULT 0.0,
            rp_5             REAL NOT NULL DEFAULT 0.0,
            rp_15            REAL NOT NULL DEFAULT 0.0,
            rp_20            REAL NOT NULL DEFAULT 0.0,
            max_30d_rain     REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS station_rainfall_history (
            station_id   INTEGER NOT NULL,
            date         TEXT NOT NULL,
            rainfall_mm  REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (station_id, date),
            FOREIGN KEY (station_id) REFERENCES station_static(station_id)
        );

        CREATE TABLE IF NOT EXISTS gauge_state (
            station_id      INTEGER NOT NULL,
            date            TEXT NOT NULL,
            raw_streamflow  REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (station_id, date),
            FOREIGN KEY (station_id) REFERENCES station_static(station_id)
        );

        CREATE TABLE IF NOT EXISTS station_flow_percentiles (
            station_id        INTEGER PRIMARY KEY,
            percentile_values TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (station_id) REFERENCES station_static(station_id)
        );
    """)
    conn.commit()
    print("✅ Database tables initialized.")


def execute(sql: str, params: list = None):
    """Execute a write query."""
    conn = _get_conn()
    if params:
        conn.execute(sql, params)
    else:
        conn.execute(sql)
    conn.commit()


def executemany(sql: str, params_list: list):
    """Execute a write query for many rows."""
    conn = _get_conn()
    conn.executemany(sql, params_list)
    conn.commit()


def query(sql: str, params: list = None) -> list[dict]:
    """Execute a read query and return list of dicts."""
    conn = _get_conn()
    if params:
        cursor = conn.execute(sql, params)
    else:
        cursor = conn.execute(sql)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def query_one(sql: str, params: list = None) -> dict | None:
    """Execute a read query and return a single dict or None."""
    results = query(sql, params)
    return results[0] if results else None


def get_station(station_id: int) -> dict | None:
    """Get a single station from station_static."""
    return query_one("SELECT * FROM station_static WHERE station_id = ?", [station_id])


def get_all_stations() -> list[dict]:
    """Get all stations from station_static."""
    return query("SELECT * FROM station_static ORDER BY station_id")


def get_station_count() -> int:
    """Get the number of stations."""
    result = query_one("SELECT COUNT(*) as cnt FROM station_static")
    return result["cnt"] if result else 0


def get_rainfall_history(station_id: int) -> list[dict]:
    """Get rainfall history for a station, ordered by date ASC."""
    return query(
        "SELECT date, rainfall_mm FROM station_rainfall_history "
        "WHERE station_id = ? ORDER BY date ASC",
        [station_id]
    )


def get_rainfall_for_date(station_id: int, date_str: str) -> float | None:
    """Get rainfall for a specific date and station, if exists."""
    row = query_one(
        "SELECT rainfall_mm FROM station_rainfall_history WHERE station_id = ? AND date = ?",
        [station_id, date_str]
    )
    return row["rainfall_mm"] if row else None


def get_gauge_state(station_id: int, limit: int = 2, before_date: str | None = None) -> list[dict]:
    """Get latest gauge_state rows for a station, ordered by date DESC.

    Args:
        station_id: station to query
        limit: max rows to return
        before_date: if provided, only return rows with date < before_date
                     (use target_date to avoid reading back the current run's output)
    """
    if before_date:
        return query(
            "SELECT date, raw_streamflow FROM gauge_state "
            "WHERE station_id = ? AND date < ? ORDER BY date DESC LIMIT ?",
            [station_id, before_date, limit]
        )
    return query(
        "SELECT date, raw_streamflow FROM gauge_state "
        "WHERE station_id = ? ORDER BY date DESC LIMIT ?",
        [station_id, limit]
    )


def insert_rainfall(station_id: int, date_str: str, rainfall_mm: float):
    """Insert a rainfall record (ignore if exists)."""
    execute(
        "INSERT OR IGNORE INTO station_rainfall_history (station_id, date, rainfall_mm) "
        "VALUES (?, ?, ?)",
        [station_id, date_str, rainfall_mm]
    )


def cleanup_old_rainfall(station_id: int, cutoff_date: str):
    """Delete rainfall records older than cutoff_date for a station."""
    execute(
        "DELETE FROM station_rainfall_history WHERE station_id = ? AND date < ?",
        [station_id, cutoff_date]
    )


def insert_gauge_state(station_id: int, date_str: str, raw_streamflow: float):
    """Insert a gauge_state record (replace if exists)."""
    execute(
        "INSERT OR REPLACE INTO gauge_state (station_id, date, raw_streamflow) "
        "VALUES (?, ?, ?)",
        [station_id, date_str, raw_streamflow]
    )


def cleanup_old_gauge_state(station_id: int, cutoff_date: str):
    """Delete gauge_state records older than cutoff_date for a station."""
    execute(
        "DELETE FROM gauge_state WHERE station_id = ? AND date < ?",
        [station_id, cutoff_date]
    )


def update_max_30d_rain(station_id: int, max_30d_rain: float):
    """Update max_30d_rain in station_static."""
    execute(
        "UPDATE station_static SET max_30d_rain = ? WHERE station_id = ?",
        [max_30d_rain, station_id]
    )


def get_flow_percentiles(station_id: int) -> list[float]:
    """Get flow percentile values for a station."""
    row = query_one(
        "SELECT percentile_values FROM station_flow_percentiles WHERE station_id = ?",
        [station_id]
    )
    if row:
        return json.loads(row["percentile_values"])
    return []


def update_flow_percentiles(station_id: int, values: list[float]):
    """Update flow percentile values for a station."""
    execute(
        "INSERT OR REPLACE INTO station_flow_percentiles (station_id, percentile_values) "
        "VALUES (?, ?)",
        [station_id, json.dumps(values)]
    )


def check_and_reset_database_if_needed():
    """Checks if the database contains old (March 2026) data, and drops/re-creates everything if so."""
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # Check if table gauge_state exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gauge_state'")
        if not cursor.fetchone():
            return
        
        # Check if there is any row with date containing '2026-03'
        cursor.execute("SELECT COUNT(*) as cnt FROM gauge_state WHERE date LIKE '2026-03-%'")
        row = cursor.fetchone()
        if row and row[0] > 0:
            print("⚠️ Old database detected (March 2026 data). Resetting database to start fresh with July 10, 2026 data...")
            conn.close()
            try:
                os.remove(DB_PATH)
                print("🗑️ Existing flood_prediction.db deleted.")
            except Exception as e:
                print(f"⚠️ Could not delete database file ({e}), dropping tables instead...")
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DROP TABLE IF EXISTS station_rainfall_history")
                conn.execute("DROP TABLE IF EXISTS gauge_state")
                conn.execute("DROP TABLE IF EXISTS station_flow_percentiles")
                conn.execute("DROP TABLE IF EXISTS station_static")
                conn.commit()
                conn.close()
    except Exception as e:
        print(f"⚠️ Error checking/resetting database: {e}")
    finally:
        try:
            conn.close()
        except:
            pass

