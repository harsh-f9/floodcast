"""Background jobs for long agentic runs (SQLite table + worker thread + polling).

Why: a 378-station sweep outlives any HTTP request budget. POST /api/chat/jobs
returns 202 {job_id} immediately; a single worker thread runs the full agent
loop; GET /api/chat/jobs/{id} polls status/progress/events/result. SQLite WAL
is the store (zero new infra); the worker picks up `queued` rows on boot so a
restart re-runs interrupted jobs. Render web services (long-lived) run this
fine; Vercel serverless functions cannot (use Render).

Concurrency: one worker (torch singleton + SQLite). Concurrent submits queue.
"""
import contextvars
import json
import logging
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("chat_agent.jobs")

_job_id: contextvars.ContextVar[str] = contextvars.ContextVar("chat_job", default="")


def current_job() -> str:
    return _job_id.get()


def _db_path() -> str:
    try:
        import Flood_prediction.database as flood_db  # type: ignore
    except ImportError:
        import database as flood_db  # type: ignore
    return flood_db.DB_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_table():
    conn = _conn()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS chat_jobs(
              id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              status TEXT NOT NULL DEFAULT 'queued',
              progress_done INTEGER NOT NULL DEFAULT 0,
              progress_total INTEGER NOT NULL DEFAULT 0,
              progress_note TEXT NOT NULL DEFAULT '',
              question TEXT NOT NULL DEFAULT '',
              messages_json TEXT NOT NULL DEFAULT '[]',
              horizon_days INTEGER NOT NULL DEFAULT 7,
              events_json TEXT NOT NULL DEFAULT '[]',
              result_json TEXT NOT NULL DEFAULT '',
              error TEXT NOT NULL DEFAULT '')"""
        )
        cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_jobs)").fetchall()}
        if "horizon_days" not in cols:
            conn.execute("ALTER TABLE chat_jobs ADD COLUMN horizon_days INTEGER NOT NULL DEFAULT 7")
        if "messages_json" not in cols:
            conn.execute("ALTER TABLE chat_jobs ADD COLUMN messages_json TEXT NOT NULL DEFAULT '[]'")
        conn.commit()
    finally:
        conn.close()


MAX_EVENTS = 300
MAX_NONTERMINAL_JOBS = 3  # queue depth cap; submitter gets 429 beyond this


class QueueFullError(Exception):
    pass


_cancel_events: dict = {}
_cancel_lock = threading.Lock()


def _cancel_event(job_id: str) -> threading.Event:
    with _cancel_lock:
        return _cancel_events.setdefault(job_id, threading.Event())


def cancel(job_id: str) -> bool:
    """Request cancellation; the sweep loop checks between stations."""
    job = get_job(job_id)
    if not job or job.get("status") not in ("queued", "running"):
        return False
    _cancel_event(job_id).set()
    _write(job_id, status="cancelled", error="cancelled by user")
    return True


def cancelled(job_id: str) -> bool:
    if not job_id:
        return False
    with _cancel_lock:
        evt = _cancel_events.get(job_id)
    return bool(evt and evt.is_set())


def nonterminal_count() -> int:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM chat_jobs "
            "WHERE status IN ('queued','running')").fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


def shutdown():
    _executor.shutdown(wait=False, cancel_futures=True)


def _write(job_id: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = _conn()
    try:
        conn.execute(f"UPDATE chat_jobs SET {cols} WHERE id = ?", [*fields.values(), job_id])
        conn.commit()
    finally:
        conn.close()


def record_event(job_id: str, evt: dict):
    conn = _conn()
    try:
        row = conn.execute("SELECT events_json FROM chat_jobs WHERE id = ?", [job_id]).fetchone()
        events = json.loads(row["events_json"]) if row and row["events_json"] else []
        events.append(evt)
        conn.execute("UPDATE chat_jobs SET events_json = ? WHERE id = ?",
                     [json.dumps(events[-MAX_EVENTS:]), job_id])
        conn.commit()
    except Exception as e:
        log.warning("job event record failed: %s", e)
    finally:
        conn.close()


def set_progress(job_id: str, done: int, total: int, note: str = ""):
    _write(job_id, status="running", progress_done=done, progress_total=total,
           progress_note=note[:200])


def get_job(job_id: str) -> dict | None:
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM chat_jobs WHERE id = ?", [job_id]).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ChatJob")


def _run(job_id: str, messages: list, horizon_days: int):
    from .agent import run_agent
    from .log import bind as _bind

    _bind(job_id[:8])
    _job_id.set(job_id)
    try:
        if cancelled(job_id):
            _write(job_id, status="cancelled", error="cancelled before start")
            return
        _write(job_id, status="running")

        def _hook(evt: dict):
            record_event(job_id, evt)

        out = run_agent(messages, horizon_days=horizon_days, request_id=job_id[:8],
                        on_event=_hook)
        if cancelled(job_id):
            _write(job_id, status="cancelled", error="cancelled during run")
        else:
            _write(job_id, status="done", result_json=json.dumps(out, default=str)[:200000])
    except Exception as e:
        log.exception("job %s failed", job_id)
        _write(job_id, status="failed", error=str(e)[:500])
    finally:
        _job_id.set("")
        from .log import bind as _rebind

        _rebind("-")
        with _cancel_lock:
            _cancel_events.pop(job_id, None)


def submit(messages: list, horizon_days: int = 7) -> str:
    init_table()
    if nonterminal_count() >= MAX_NONTERMINAL_JOBS:
        raise QueueFullError(
            f"Too many active jobs (max {MAX_NONTERMINAL_JOBS}). Wait and retry.")
    job_id = uuid.uuid4().hex[:12]
    trimmed = messages[-20:] if isinstance(messages, list) else []
    question = next((m.get("content", "") for m in reversed(trimmed)
                     if m.get("role") == "user"), "")[:300]
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO chat_jobs (id, status, question, messages_json, horizon_days) "
            "VALUES (?, 'queued', ?, ?, ?)",
            [job_id, question, json.dumps(trimmed), int(horizon_days)],
        )
        conn.commit()
    finally:
        conn.close()
    _executor.submit(_run, job_id, trimmed, horizon_days)
    return job_id


def resume_interrupted():
    """Re-queue jobs left running/queued by a previous process (call at boot)."""
    try:
        init_table()
    except Exception as e:
        print(f"chat jobs init skipped: {e}")
        return
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, messages_json, horizon_days FROM chat_jobs "
            "WHERE status IN ('queued','running')").fetchall()
        pending = [(r["id"], r["messages_json"], r["horizon_days"] or 7) for r in rows]
    finally:
        conn.close()
    for jid, msgs, hz in pending:
        try:
            messages = json.loads(msgs) if msgs else []
        except Exception:
            messages = []
        if not messages:
            _write(jid, status="failed", error="interrupted; original messages lost")
            continue
        _write(jid, status="queued", error="", events_json="[]",
               progress_note="resumed after restart")
        _executor.submit(_run, jid, messages, hz)
    if pending:
        print(f"chat jobs resumed: {len(pending)} re-queued.")
