"""Request-scoped structured logging for the chat agent.

Every log line is one JSON object on stdout (Render captures stdout), carrying
the request id so a full diagnosis trail for one user query can be grepped:

  {"ts": ..., "rid": "a1b2c3d4", "stage": "predict.station", ...}

Stages: chat.request/intent/scope_reject, tool.start/tool.done,
predict.station, briefing.done, llm.request/llm.response/llm.repair,
sql.denied/sql.done, summary.request/summary.done, chat.response.

Usage: router binds one id per request with `bind(rid)`; any module logs with
`event(stage, **fields)` and the current id is attached automatically.
"""
import contextvars
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("chat_agent")

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("chat_rid", default="-")


def bind(rid: str):
    return _request_id.set(rid)


def rid() -> str:
    return _request_id.get()


def event(stage: str, level: int = logging.INFO, **fields):
    try:
        payload = {"ts": datetime.now(timezone.utc).isoformat(),
                   "rid": _request_id.get(), "stage": stage}
        for k, v in fields.items():
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = str(v)[:500]
        log.log(level, json.dumps(payload, default=str)[:4000])
    except Exception:
        pass
