"""001 baseline: 4 tables from database.init_tables(). No-op, records version 1."""


def migrate(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    cur = conn.execute("SELECT MAX(version) AS v FROM schema_migrations")
    row = cur.fetchone()
    if not row or row[0] is None or row[0] < 1:
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, datetime('now'))"
        )
