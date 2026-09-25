"""Request/response schemas for POST /api/chat."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    horizon_days: int = Field(default=7, ge=1, le=7)


class ChartPayload(BaseModel):
    station_id: int
    station_name: str = ""
    district: str = ""
    thresholds: dict = {}
    chart: list[dict] = []
    severity: str = ""
    peak_flow: Optional[float] = None
    peak_date: str = ""


class ToolTrace(BaseModel):
    tool: str
    args: dict = {}
    ok: bool = True
    error: str = ""


class ChatResponse(BaseModel):
    reply: str
    raw_reply: str = ""
    tool_trace: list[ToolTrace] = []
    charts: list[ChartPayload] = []
    briefing: Optional[str] = None
    model: str = ""
    llm_used: bool = False
    summary_used: bool = False
    summary_model: str = ""

    model_config = {"extra": "ignore"}


class StatusResponse(BaseModel):
    enabled: bool
    llm_configured: bool
    model: str
    districts: int

    model_config = {"extra": "ignore"}
