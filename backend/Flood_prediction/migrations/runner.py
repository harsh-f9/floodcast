"""Migration runner: applies NNN_*.py in order, tracks schema_migrations."""
import os
import re
import sqlite3
import importlib


def _applied(conn):
    try:
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        return set()


def run_migrations(db_path: str | None = None):
    from Flood_prediction import database as db

    path = db_path or db.DB_PATH
    mig_dir = os.path.dirname(os.path.abspath(__file__))
    files = sorted(f for f in os.listdir(mig_dir) if re.match(r"^\d{3}_.*\.py$", f))
    conn = sqlite3.connect(path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        for f in files:
            ver = int(f[:3])
            if ver in _applied(conn):
                continue
            mod = importlib.import_module(f"Flood_prediction.migrations.{f[:-3]}")
            mod.migrate(conn)
        conn.commit()
    finally:
        conn.close()
