"""Read-only SQL executor — the second, independent safety layer.

Even if the sqlglot guard were bypassed, this layer enforces safety at the
database boundary:
  - dedicated connection opened in SQLite read-only URI mode (writes fail
    inside SQLite itself, verified by test),
  - statement timeout via a progress handler (runaway queries aborted),
  - hard row cap with a truncation flag,
  - every execution recorded to the audit log.

Fail closed: any error returns a denial dict, never raises internals.
"""
import logging
import sqlite3
import time

from .schema import MAX_SQL_ROWS
from .sql_guard import validate_sql

STATEMENT_TIMEOUT_S = 5.0

log = logging.getLogger("chat_agent.sql")


def _db_path() -> str:
    try:
        import Flood_prediction.database as flood_db  # type: ignore
    except ImportError:
        import database as flood_db  # type: ignore
    return flood_db.DB_PATH


def _ro_connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    deadline = time.monotonic() + STATEMENT_TIMEOUT_S

    def _progress():
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(_progress, 1000)
    return conn


def execute_sql(sql: str) -> dict:
    """Validate (guard) then execute read-only. Returns a plain dict."""
    t0 = time.monotonic()
    ok, errors, normalized = validate_sql(sql)
    if not ok:
        log.warning("sql denied: %s | %s", sql[:200], errors)
        return {"ok": False, "error": "; ".join(errors), "sql": sql[:500],
                "columns": [], "rows": [], "row_count": 0, "truncated": False}
    conn = None
    try:
        conn = _ro_connect(_db_path())
        cur = conn.execute(normalized)
        columns = [d[0] for d in (cur.description or [])]
        raw = cur.fetchmany(MAX_SQL_ROWS + 1)
        truncated = len(raw) > MAX_SQL_ROWS
        rows = [dict(r) for r in raw[:MAX_SQL_ROWS]]
        elapsed = round(time.monotonic() - t0, 2)
        log.info("sql ok rows=%d truncated=%s %.2fs | %s",
                 len(rows), truncated, elapsed, normalized[:200])
        return {"ok": True, "error": "", "sql": normalized,
                "columns": columns, "rows": rows,
                "row_count": len(rows), "truncated": truncated}
    except Exception as e:
        log.warning("sql exec failed: %s | %s", normalized[:200], e)
        return {"ok": False, "error": f"Execution failed: {e}",
                "sql": normalized, "columns": [], "rows": [],
                "row_count": 0, "truncated": False}
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
