"""002 trust layer: additive freshness + flags. Idempotent, Render-safe.

Adds ingested_at/source to rainfall + gauge_state (defaults backfill),
creates quality_flags(station_id,date,flag,detail). Never drops. Guarded via
PRAGMA table_info (SQLite has no ADD COLUMN IF NOT EXISTS).
"""


def _cols(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    if "station_rainfall_history" in {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        rh = _cols(conn, "station_rainfall_history")
        if "ingested_at" not in rh:
            conn.execute("ALTER TABLE station_rainfall_history ADD COLUMN ingested_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00'")
        if "source" not in rh:
            conn.execute("ALTER TABLE station_rainfall_history ADD COLUMN source TEXT NOT NULL DEFAULT 'backfill-unknown'")
    if "gauge_state" in {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        gs = _cols(conn, "gauge_state")
        if "ingested_at" not in gs:
            conn.execute("ALTER TABLE gauge_state ADD COLUMN ingested_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00'")
        if "source" not in gs:
            conn.execute("ALTER TABLE gauge_state ADD COLUMN source TEXT NOT NULL DEFAULT 'backfill-unknown'")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quality_flags(
          station_id INTEGER NOT NULL, date TEXT NOT NULL, flag TEXT NOT NULL,
          detail TEXT NOT NULL DEFAULT '{}',
          PRIMARY KEY (station_id, date, flag),
          FOREIGN KEY (station_id) REFERENCES station_static(station_id))"""
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, datetime('now'))"
    )
