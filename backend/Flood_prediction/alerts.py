"""Telegram alert webhook (migratable, additive, Phase 05 part).

Standalone router. Delete this file + one include line to remove feature.
Log-only stub when env missing (no external dependency to boot).

Wiring (one line, do in Phase 05 ship with main.py rewrite):
    from Flood_prediction.alerts import router as alerts_router
    app.include_router(alerts_router)

Env:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Endpoint:
    POST /api/admin/alert-webhook {station_id:int, date:str, flow:float, severity:str}
    Forwards DANGER/EXTREME to Telegram; else returns {sent:false}.
"""

import os

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
    _HAS_FASTAPI = True
except Exception:
    APIRouter = None  # type: ignore
    HTTPException = Exception  # type: ignore
    BaseModel = object  # type: ignore
    _HAS_FASTAPI = False


if _HAS_FASTAPI:
    class AlertIn(BaseModel):
        station_id: int
        date: str
        flow: float
        severity: str

    router = APIRouter()

    @router.post("/api/admin/alert-webhook")
    def alert_webhook(req: AlertIn):
        sev = (req.severity or "").upper()
        if sev not in ("DANGER", "EXTREME"):
            return {"sent": False, "reason": f"severity {sev} below threshold"}
        try:
            from Flood_prediction.validation import validate_date, validate_streamflow
        except ImportError:
            try:
                from validation import validate_date, validate_streamflow
            except ImportError:
                validate_date = lambda s: s  # type: ignore
                validate_streamflow = lambda v: float(v)  # type: ignore
        try:
            validate_date(req.date)
            validate_streamflow(req.flow)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_CHAT_ID")
        text = f"Flood {sev}: station {req.station_id} flow {req.flow} m3/s on {req.date}"
        if not token or not chat:
            print(f"alert-log-only: {text}")
            return {"sent": False, "reason": "TELEGRAM_* env missing (log-only stub)"}
        try:
            import httpx  # lazy: backend dep, not import-time

            r = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
                timeout=10.0,
            )
            r.raise_for_status()
            return {"sent": True, "severity": sev}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"telegram send failed: {e}")
else:
    router = None
