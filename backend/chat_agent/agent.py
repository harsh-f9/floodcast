"""Agent loop: OpenRouter Chat Completions + native tools, tool-only behavior.

Layers (agent-heavy, but each layer is small):
  L0 local scope gate  — out-of-scope queries get the fixed fallback, no LLM cost.
  L1 intent parse      — deterministic district/station/keyword extraction.
  L2 tool loop         — OpenRouter (if key present) or deterministic fallback.
  L3 reply assembly    — reply text + Recharts-ready charts + briefing paragraph.

The LLM never answers from knowledge: it must call a tool to say anything
about flows, and L1 guarantees charts deploy even if the model chatters.
"""
import json
import os
import re
import time

import httpx

from . import district_map
from .schema import schema_prompt
from .tools import (
    FALLBACK_REPLY,
    CANNED_MAX_RP,
    CANNED_TOP_FLOW,
    TOOL_SCHEMAS,
    charts_from_rows,
    district_stations,
    predict_district,
    run_tool,
    station_history,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"  # tool loop; override via OPENROUTER_MODEL
DEFAULT_SUMMARY_MODEL = "nvidia/nemotron-3.5-lightning"  # summarizer layer; override via OPENROUTER_SUMMARY_MODEL
FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b"  # paid rescue; override via OPENROUTER_FALLBACK_MODEL
MAX_TOOL_ROUNDS = 10  # generous: validation-repair cycles must never starve
LLM_TIMEOUT_S = 120.0  # free-tier models can be slow; wait rather than fail
LLM_MAX_TOKENS = 20000
SUMMARY_MAX_TOKENS = 20000
PRIMARY_ATTEMPTS = 2  # tries on the free model before paid rescue
FALLBACK_ATTEMPTS = 2

SYSTEM_PROMPT = """You are the CRO Flood Assistant, a narrow tool for Uttar Pradesh flood streamflow.
Rules:
- You ONLY answer using the provided tools (predict_district, station_history,
  district_stations, describe_tables, run_sql).
- Never invent streamflow numbers, dates, severities, or station ids. If a tool was not called, say you cannot answer.
- If the user asks anything outside flood predictions / station history / gauge listings / database analytics, reply exactly: I can't answer that — I can only show flood predictions and station history.
- Keep replies short. Always name station ids, dates, and severity labels returned by the tools.
- District names must match tool results; never guess spellings.
- For cross-station analytics (top-N, highest/lowest, comparisons, history ranges) write SQLite with run_sql:
  single SELECT only, explicit columns (never *), LIMIT <= 100. If run_sql
  returns an error, rewrite the SQL using the error message and retry.
- For graphs of specific stations after an analytics query, call
  station_history per station.

{schema}"""

SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{schema}", schema_prompt())


def model_name() -> str:
    return os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)


def summary_model_name() -> str:
    return os.environ.get("OPENROUTER_SUMMARY_MODEL", DEFAULT_SUMMARY_MODEL)


def fallback_model_name() -> str:
    return os.environ.get("OPENROUTER_FALLBACK_MODEL", FALLBACK_MODEL)


def llm_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


# ── L0: scope gate ─────────────────────────────────────────────────────────

_SCOPE_RE = re.compile(
    r"flood|streamflow|predict|forecast|history|station|district|gauge|"
    r"rain|risk|report|severity|warning|danger|watch|extreme|normal|flow|"
    r"water|river|discharge|\brp\b|threshold|top|highest|most|max|sql|graph|"
    r"\bhi\b|hello|help|namaste",
    re.IGNORECASE,
)
_STATION_RE = re.compile(r"station\s+(\d+)", re.IGNORECASE)


def in_scope(text: str) -> bool:
    return bool(_SCOPE_RE.search(text or ""))


# ── L1: deterministic intent parse ─────────────────────────────────────────

_DAYS_RE = re.compile(r"(?:past|last)\s+(\d+)\s+days?", re.IGNORECASE)
_TOP_RE = re.compile(r"\btop\s+(\d+)\b|\bhighest\b|\bmost\b|\bmax(?:imum)?\b", re.IGNORECASE)
_RP_RE = re.compile(r"\brp\b|return period|threshold", re.IGNORECASE)


def _parse_days(text: str, default: int) -> int:
    m = _DAYS_RE.search(text or "")
    if m:
        try:
            return max(1, min(int(m.group(1)), 7))
        except ValueError:
            pass
    return default


def parse_intent(text: str) -> dict:
    """kinds: predict/history/info/sql_top/sql_rp/none (+ days, top_n)."""
    lower = (text or "").lower()
    districts = [d for d in district_map.all_districts() if d.lower() in lower]
    m = _STATION_RE.search(text or "")
    station_id = int(m.group(1)) if m else None
    wants_history = bool(re.search(r"histor|past|previous|old|last\s+\d*\s*day|ago|graph", lower))
    wants_predict = bool(re.search(r"predict|forecast|risk|report|future|next\s+\d*\s*day|warn|danger", lower))
    wants_info = bool(re.search(r"list|stations|gauges|which|where|threshold|show.*gauge", lower))
    wants_top = bool(_TOP_RE.search(text or "") and re.search(r"flow|stream|flood|station|gauge", lower))
    wants_rp = bool(_RP_RE.search(text or ""))
    if wants_rp and wants_top:
        return {"kind": "sql_rp", "districts": districts, "station_id": station_id,
                "days": _parse_days(text, 3), "top_n": 5}
    if wants_top:
        n = re.search(r"\btop\s+(\d+)\b", lower)
        top_n = max(1, min(int(n.group(1)) if n else 5, 10))
        return {"kind": "sql_top", "districts": districts, "station_id": station_id,
                "days": _parse_days(text, 3), "top_n": top_n}
    if wants_history and station_id is not None:
        return {"kind": "history", "districts": districts, "station_id": station_id,
                "days": _parse_days(text, 7), "top_n": 5}
    if wants_predict and districts:
        return {"kind": "predict", "districts": districts, "station_id": station_id,
                "days": 7, "top_n": 5}
    if wants_info:
        return {"kind": "info", "districts": districts, "station_id": station_id,
                "days": 7, "top_n": 5}
    if districts:  # bare district name -> predict (most useful default)
        return {"kind": "predict", "districts": districts, "station_id": station_id,
                "days": 7, "top_n": 5}
    if station_id is not None:  # bare station id -> history
        return {"kind": "history", "districts": districts, "station_id": station_id,
                "days": _parse_days(text, 7), "top_n": 5}
    return {"kind": "none", "districts": districts, "station_id": station_id,
            "days": 7, "top_n": 5}


def capability_reply() -> str:
    names = district_map.all_districts()
    return (
        "I can show flood predictions and station history. "
        f"Try 'Predict Bijnor', 'History of station 0', or 'List stations in Lucknow'. "
        f"({len(names)} districts available.)"
    )


# ── L2: OpenRouter tool loop ───────────────────────────────────────────────

SUMMARY_SYSTEM = """You summarize flood-assistant tool results for a district officer.
Rules:
- Summarize ONLY the tool results given below. Never invent stations, numbers, dates, or severities.
- Output short markdown: 2-4 bullets with the key facts (peak station/flow/date, severity counts, action).
- Cite visuals inline as [Chart 1], [Chart 2], matching the chart list order given.
- If results contain an error, say what failed in one line."""


def _post_chat(messages: list, tools: list | None, model: str, max_tokens: int) -> tuple:
    """POST with paid-model rescue. Returns (data, served_model).

    The free primary is always tried first (so it serves ~all traffic);
    only traffic/availability failures (429/5xx/timeout/transport, or a 404
    meaning the model slug is gone) switch a layer to the paid fallback.
    Auth/billing/malformed errors (401/402/403/400) raise immediately —
    retrying those can never succeed.
    """
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "X-Title": "CRO Flood Assistant",
    }
    rescue = fallback_model_name()
    candidates = [(model, PRIMARY_ATTEMPTS)]
    if rescue and rescue != model:
        candidates.append((rescue, FALLBACK_ATTEMPTS))
    last_err = "no attempt"
    for cand, tries in candidates:
        body = {
            "model": cand,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        for attempt in range(tries):
            try:
                r = httpx.post(OPENROUTER_URL, headers=headers, json=body, timeout=LLM_TIMEOUT_S)
                if r.status_code in (429, 500, 502, 503):
                    last_err = f"openrouter {r.status_code} on {cand}"
                    time.sleep(2 * (2 ** attempt))
                    continue
                if r.status_code == 404:
                    last_err = f"openrouter 404 on {cand}"
                    break  # slug gone — try next candidate, don't burn retries
                r.raise_for_status()
                if cand != model:
                    print(f"chat fallback served by {cand} (primary: {last_err})")
                return r.json(), cand
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"OpenRouter error: {e.response.status_code}") from e
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_err = f"{type(e).__name__} on {cand}: {e}"
                time.sleep(2 * (2 ** attempt))
    raise RuntimeError(f"OpenRouter unreachable after retries ({last_err}).")


def _summarize(user_text: str, reply: str, charts: list, briefings: list) -> tuple:
    """Summarizer layer: separate model, no tools. Failover keeps raw reply."""
    desc = []
    for n, c in enumerate(charts[:6], 1):
        pts = c.get("chart", []) or []
        dates = [p["date"] for p in pts if p.get("date")]
        desc.append(
            f"[Chart {n}] station {c.get('station_id')} ({c.get('district', '')}), "
            f"severity {c.get('severity', '')}, peak {c.get('peak_flow')} m3/s on "
            f"{c.get('peak_date', '')}, {len(pts)} points"
            + (f" ({dates[0]}..{dates[-1]})" if dates else "")
        )
    if len(charts) > 6:
        desc.append(f"({len(charts) - 6} more charts omitted)")
    context = (
        f"User question: {user_text}\n\nTool-grounded answer:\n{reply}\n\n"
        f"Visuals:\n" + ("\n".join(desc) if desc else "(no charts)") + "\n\n"
        f"Briefing: {' '.join(briefings) if briefings else '(none)'}"
    )
    for _ in range(2):  # empty completions happen on free tiers; one retry
        try:
            data, served_summary_model = _post_chat(
                [{"role": "system", "content": SUMMARY_SYSTEM},
                 {"role": "user", "content": context}],
                None, summary_model_name(), SUMMARY_MAX_TOKENS,
            )
            text = (data["choices"][0]["message"].get("content") or "").strip()
            if text:
                return text, True, served_summary_model
        except Exception as e:
            print(f"summarizer skipped: {e}")
            break
    return reply, False, ""


def run_agent(messages: list, horizon_days: int = 7) -> dict:
    """Full loop. messages = [{role, content}] with last = current user query."""
    t0 = time.time()
    user_text = messages[-1]["content"] if messages else ""

    # L0: scope gate — no LLM cost for random questions.
    if not in_scope(user_text):
        return {
            "reply": FALLBACK_REPLY, "raw_reply": FALLBACK_REPLY,
            "tool_trace": [], "charts": [],
            "briefing": None, "model": model_name(), "llm_used": False,
            "summary_used": False, "summary_model": "",
            "latency_s": 0.0,
        }
    if re.match(r"^\s*(hi|hello|hey|namaste|help)\s*[?.!]*\s*$", user_text, re.IGNORECASE):
        return {
            "reply": capability_reply(), "raw_reply": capability_reply(),
            "tool_trace": [], "charts": [],
            "briefing": None, "model": model_name(), "llm_used": False,
            "summary_used": False, "summary_model": "",
            "latency_s": 0.0,
        }

    intent = parse_intent(user_text)
    trace: list = []
    charts: list = []
    briefings: list = []
    _tables: list = []

    def _record(tool: str, args: dict):
        try:
            out = run_tool(tool, args)
            ok = not (isinstance(out, dict) and out.get("ok") is False)
            trace.append({"tool": tool, "args": args, "ok": ok,
                          "error": "" if ok else str(out.get("error", ""))[:300]})
            _collect(tool, out)
            return out
        except Exception as e:
            trace.append({"tool": tool, "args": args, "ok": False, "error": str(e)[:300]})
            return {"error": str(e)[:300]}

    def _collect(tool: str, out: dict):
        if not isinstance(out, dict) or "error" in out:
            return
        if tool == "run_sql":
            rows = out.get("rows", []) or []
            _tables.append({"columns": out.get("columns", []), "rows": rows[:10]})
            for c in charts_from_rows(rows, out.get("columns", [])):
                if c["station_id"] not in {x["station_id"] for x in charts}:
                    charts.append(c)
            return
        if tool == "predict_district":
            for d in out.get("results", []):
                briefings.append(d.get("briefing", ""))
                for s in d.get("stations", []):
                    charts.append({
                        "station_id": s["station_id"],
                        "station_name": s.get("station_name", ""),
                        "district": d.get("district", ""),
                        "thresholds": s.get("thresholds", {}),
                        "chart": s.get("chart", []),
                        "severity": s.get("severity", ""),
                        "peak_flow": s.get("peak_flow"),
                        "peak_date": s.get("peak_date", ""),
                    })
        elif tool == "station_history":
            charts.append({
                "station_id": out.get("station_id", -1),
                "station_name": out.get("station_name", ""),
                "district": out.get("district", ""),
                "thresholds": out.get("thresholds", {}),
                "chart": out.get("chart", []),
                "severity": (out.get("history") or [{}])[-1].get("severity", "") if out.get("history") else "",
                "peak_flow": max([h["streamflow"] for h in out.get("history", [])] or [0.0]),
                "peak_date": (out.get("history") or [{}])[-1].get("date", "") if out.get("history") else "",
            })

    reply = ""
    llm_used = False
    tool_model = model_name()

    if llm_configured():
        convo = [{"role": "system", "content": SYSTEM_PROMPT}]
        convo += [{"role": m["role"], "content": m["content"]} for m in messages[-10:]]
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                data, tool_model = _post_chat(convo, TOOL_SCHEMAS, model_name(), LLM_MAX_TOKENS)
                msg = data["choices"][0]["message"]
                calls = msg.get("tool_calls") or []
                if msg.get("content"):
                    reply = msg["content"]
                if not calls:
                    break
                convo.append({
                    "role": "assistant", "content": msg.get("content") or "",
                    "tool_calls": calls,
                })
                for c in calls:
                    args = json.loads(c["function"].get("arguments") or "{}")
                    if c["function"]["name"] == "predict_district":
                        args.setdefault("horizon_days", horizon_days)
                    out = _record(c["function"]["name"], args)
                    convo.append({
                        "role": "tool", "tool_call_id": c["id"],
                        "content": json.dumps(out)[:6000],
                    })
            llm_used = True
        except Exception as e:
            reply = f"Assistant service issue ({e}). Falling back to direct tools."

    # Deterministic guarantee: if LLM missing/unused/failed, run parsed intent directly.
    if not trace and intent["kind"] != "none":
        if intent["kind"] == "predict":
            _record("predict_district", {"districts": intent["districts"][:2], "horizon_days": horizon_days})
        elif intent["kind"] == "history":
            _record("station_history", {"station_id": intent["station_id"], "days": intent["days"]})
        elif intent["kind"] == "info":
            _record("district_stations", {"district": (intent["districts"][:1] or [None])[0]})
        elif intent["kind"] == "sql_top":
            top = _record("run_sql", {"sql": CANNED_TOP_FLOW})
            for row in (top.get("rows", []) or [])[: intent["top_n"]]:
                try:
                    _record("station_history",
                            {"station_id": int(row["station_id"]), "days": intent["days"]})
                except (TypeError, ValueError, KeyError):
                    continue
        elif intent["kind"] == "sql_rp":
            _record("run_sql", {"sql": CANNED_MAX_RP})

    errors = [t for t in trace if not t["ok"]]
    if not trace:
        reply = reply or FALLBACK_REPLY
    elif errors and len(errors) == len(trace):
        reply = f"I couldn't fetch that ({errors[0]['error']}). " + capability_reply()
    elif not reply:
        reply = _template_reply(trace, charts, briefings, _tables)

    # Summarizer layer: a separate model restates the tool-grounded answer
    # with visual citations. Failover keeps the raw tool-grounded reply.
    raw_reply, summary_used, summary_model = reply, False, ""
    if trace and any(t["ok"] for t in trace) and llm_configured():
        reply, summary_used, summary_model = _summarize(user_text, reply, charts, briefings)

    return {
        "reply": reply,
        "raw_reply": raw_reply,
        "tool_trace": trace,
        "charts": charts,
        "briefing": "\n".join(b for b in briefings if b) or None,
        "model": tool_model,
        "llm_used": llm_used,
        "summary_used": summary_used,
        "summary_model": summary_model,
        "latency_s": round(time.time() - t0, 2),
    }


def _template_reply(trace: list, charts: list, briefings: list, tables: list | None = None) -> str:
    parts = []
    for t in trace:
        if t["ok"]:
            parts.append(f"• {t['tool']} {json.dumps(t['args'])[:200]} — ok")
        else:
            parts.append(f"• {t['tool']} failed: {t['error']}")
    for tab in tables or []:
        cols = tab.get("columns", [])
        rows = tab.get("rows", []) or []
        if cols and rows:
            parts.append(" | ".join(str(c) for c in cols))
            for r in rows[:10]:
                parts.append(" | ".join(str(r.get(c, "")) for c in cols))
    for c in charts[:6]:
        parts.append(
            f"Station {c['station_id']} ({c.get('district', '')}): "
            f"peak {c.get('peak_flow')} m³/s on {c.get('peak_date')} [{c.get('severity')}], "
            f"{len(c.get('chart', []))} chart points."
        )
    parts.extend(b for b in briefings if b)
    return "\n".join(parts) if parts else FALLBACK_REPLY
