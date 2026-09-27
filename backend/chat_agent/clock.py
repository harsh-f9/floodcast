"""Effective-date clock for the chat agent (kill-switch pattern applies: none —
this module has no behavior of its own).

Default is the server date in Asia/Kolkata (fixed +5:30, no tz database).
A validated client-supplied date (YYYY-MM-DD, sent by the frontend from the
user's own clock) overrides it for the duration of one run via `set_today`,
so "past few days" and staleness math anchor to the user's day, not the base
or server date. Reset in a finally block after the run.
"""
import contextvars
import re
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
_DATE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")

_override: contextvars.ContextVar[str] = contextvars.ContextVar("chat_today", default="")


def set_today(iso: str) -> str:
    """Validate + bind a client date. Returns the token to reset it, or ""."""
    if iso and _DATE_RE.match(iso):
        try:
            date.fromisoformat(iso)
            return _override.set(iso)
        except ValueError:
            pass
    return ""


def reset_today(token) -> None:
    if token:
        try:
            _override.reset(token)
        except Exception:
            pass


def today_ist() -> date:
    override = _override.get()
    if override:
        try:
            return date.fromisoformat(override)
        except ValueError:
            pass
    return datetime.now(IST).date()
