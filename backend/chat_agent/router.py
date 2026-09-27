"""POST /api/chat + GET /api/chat/status. Mounted by backend/main.py (one line).

Respects kill_switch: when disabled, /api/chat returns 503 and /api/chat/status
reports enabled=false (the frontend hides the sidebar from that flag).
"""
import logging
import time
import uuid

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
    from .log import bind as _bind_log
    from .schemas import ChatRequest, ChatResponse, JobStatusResponse, StatusResponse, ToolTrace
    from . import district_map

    router = APIRouter()
    log = logging.getLogger("chat_agent")

    import threading as _th

    _stream_lock = _th.Lock()
    _stream_inflight = [0]
    _STREAM_MAX = 2

    @router.get("/api/chat/status", response_model=StatusResponse)
    def chat_status():
        return {
            "enabled": is_enabled(),
            "llm_configured": llm_configured(),
            "model": model_name(),
            "districts": len(district_map.all_districts()),
        }

    @router.post("/api/chat/stream")
    def chat_stream(req: ChatRequest):
        """Live agentic timeline over SSE: run_started/intent/round_start/
        thinking/tool_start/tool_end/summary_*/run_finished|run_error frames,
        then a final result frame with the full ChatResponse payload."""
        import json as _json
        import queue as _queue
        import threading as _threading
        from fastapi.responses import StreamingResponse

        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        with _stream_lock:
            if _stream_inflight[0] >= _STREAM_MAX:
                raise HTTPException(status_code=429, detail={
                    "message": "Too many live streams. Use background jobs instead.",
                    "suggest_jobs": True})
            _stream_inflight[0] += 1
        rid = uuid.uuid4().hex[:8]
        q: _queue.Queue = _queue.Queue()
        _DONE = object()

        def _worker():
            _bind_log(rid)
            try:
                out = run_agent(
                    [{"role": m.role, "content": m.content} for m in req.messages],
                    horizon_days=req.horizon_days,
                    request_id=rid,
                    on_event=q.put,
                )
                q.put({"type": "result", "result": {
                    "request_id": rid,
                    "reply": out["reply"],
                    "raw_reply": out.get("raw_reply", ""),
                    "tool_trace": out.get("tool_trace", []),
                    "charts": out.get("charts", []),
                    "briefing": out.get("briefing"),
                    "model": out.get("model", ""),
                    "llm_used": out.get("llm_used", False),
                    "summary_used": out.get("summary_used", False),
                    "summary_model": out.get("summary_model", ""),
                }})
            except Exception as e:  # never leak tracebacks to the client
                log.exception("chat stream run failed")
                q.put({"type": "run_error", "error": "Chat run failed. Try again."})
            finally:
                q.put(_DONE)

        async def _gen():
            import anyio as _anyio

            _threading.Thread(target=_worker, daemon=True,
                              name=f"ChatStream-{rid}").start()
            try:
                while True:
                    try:
                        evt = await _anyio.to_thread.run_sync(q.get, cancellable=True)
                    except Exception:
                        break
                    if evt is _DONE:
                        break
                    yield f"data: {_json.dumps(evt, default=str)}\n\n"
                yield "data: {\"type\": \"stream_end\"}\n\n"
            finally:
                with _stream_lock:
                    _stream_inflight[0] = max(0, _stream_inflight[0] - 1)

        return StreamingResponse(_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    @router.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest):
        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        rid = uuid.uuid4().hex[:8]
        _bind_log(rid)
        t0 = time.time()
        try:
            out = run_agent(
                [{"role": m.role, "content": m.content} for m in req.messages],
                horizon_days=req.horizon_days,
            )
        except ValueError as e:
            if "background job" in str(e):
                raise HTTPException(status_code=429, detail={
                    "message": str(e), "suggest_jobs": True})
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
            "request_id": rid,
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

    @router.post("/api/chat/jobs", status_code=202)
    def chat_job_submit(req: ChatRequest):
        """Start a background agentic run (for multi-minute sweeps)."""
        from . import jobs as _jobs

        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        try:
            job_id = _jobs.submit(
                [{"role": m.role, "content": m.content} for m in req.messages],
                horizon_days=req.horizon_days,
            )
        except _jobs.QueueFullError as e:
            raise HTTPException(status_code=429, detail={"message": str(e),
                                                         "suggest_jobs": True})
        except Exception:
            log.exception("job submit failed")
            raise HTTPException(status_code=500, detail="Could not start job.")
        return {"job_id": job_id}

    @router.get("/api/chat/jobs/{job_id}", response_model=JobStatusResponse)
    def chat_job_status(job_id: str):
        import json as _json

        from . import jobs as _jobs

        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        job = _jobs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        try:
            events = _json.loads(job.get("events_json") or "[]")
        except Exception:
            events = []
        result = None
        if job.get("status") == "done" and job.get("result_json"):
            try:
                result = _json.loads(job["result_json"])
            except Exception:
                result = None
        return {
            "job_id": job_id,
            "status": job.get("status", ""),
            "progress_done": job.get("progress_done", 0),
            "progress_total": job.get("progress_total", 0),
            "progress_note": job.get("progress_note", ""),
            "question": job.get("question", ""),
            "events": events[-120:],
            "result": result,
            "error": job.get("error", ""),
        }

    @router.delete("/api/chat/jobs/{job_id}")
    def chat_job_cancel(job_id: str):
        from . import jobs as _jobs

        if not is_enabled():
            raise HTTPException(status_code=503, detail="Chat agent is disabled.")
        if not _jobs.cancel(job_id):
            raise HTTPException(status_code=404, detail="Job not found or already finished.")
        return {"job_id": job_id, "status": "cancelled"}
else:
    router = None
