"""POST /api/chat + GET /api/chat/status. Mounted by backend/main.py (one line).

Respects kill_switch: when disabled, /api/chat returns 503 and /api/chat/status
reports enabled=false (the frontend hides the sidebar from that flag).
"""
import logging
import time

try:
    from fastapi import APIRouter, HTTPException
    _HAS_FASTAPI = True
except Exception:
    APIRouter = None  # type: ignore
    HTTPException = Exception  # type: ignore
    _HAS_FASTAPI = False

if _HAS_FASTAPI:
    from .agent import llm_configured, model_name, run_agent
    from .kill_switch import is_enabled
    from .schemas import ChatRequest, ChatResponse, StatusResponse, ToolTrace
    from . import district_map

    router = APIRouter()
    log = logging.getLogger("chat_agent")

    @router.get("/api/chat/status", response_model=StatusResponse)
    def chat_status():
        return {
            "enabled": is_enabled(),
            "llm_configured": llm_configured(),
            "model": model_name(),
            "districts": len(district_map.all_districts()),
        }

    @router.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest):
        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        t0 = time.time()
        try:
            out = run_agent(
                [{"role": m.role, "content": m.content} for m in req.messages],
                horizon_days=req.horizon_days,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # never leak tracebacks to the client
            log.exception("chat run failed")
            raise HTTPException(status_code=500, detail="Chat run failed. Try again.")
        log.info(
            "chat ok llm=%s tools=%d charts=%d latency=%.1fs",
            out.get("llm_used"), len(out.get("tool_trace", [])),
            len(out.get("charts", [])), time.time() - t0,
        )
        return {
            "reply": out["reply"],
            "raw_reply": out.get("raw_reply", ""),
            "tool_trace": [ToolTrace(**t).model_dump() for t in out.get("tool_trace", [])],
            "charts": out.get("charts", []),
            "briefing": out.get("briefing"),
            "model": out.get("model", ""),
            "llm_used": out.get("llm_used", False),
            "summary_used": out.get("summary_used", False),
            "summary_model": out.get("summary_model", ""),
        }
else:
    router = None
