"""Feature flags for chat-agent capabilities (kill-switch pattern).

Each flag defaults ON and is toggled without code changes via env:

    CHAT_DATE_IN_PROMPT=0       # hide today's date from the system prompt
    CHAT_DISTRICT_RAINFALL=0    # disable the district_rainfall tool
    CHAT_RAINFALL_BACKFILL=0    # disable live Open-Meteo rainfall backfill (read-only mode)

To add a capability: add a flag here, gate the tool in TOOL_SCHEMAS via
tool_enabled(), and gate any prompt text on the flag. To migrate a feature
elsewhere, flip its flag off here and delete the module + tests.
"""
import os


def _flag(env_name: str, default: bool = True) -> bool:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def date_in_prompt() -> bool:
    return _flag("CHAT_DATE_IN_PROMPT", True)


def district_rainfall() -> bool:
    return _flag("CHAT_DISTRICT_RAINFALL", True)


def rainfall_backfill() -> bool:
    return _flag("CHAT_RAINFALL_BACKFILL", True)


TOOL_FLAGS = {
    "district_rainfall": district_rainfall,
    "ensure_rainfall": rainfall_backfill,
}


def tool_enabled(name: str) -> bool:
    gate = TOOL_FLAGS.get(name)
    return gate() if gate is not None else True


def active_schemas(all_schemas: list) -> list:
    """Filter OpenAI tool schemas to enabled tools only."""
    return [t for t in all_schemas if tool_enabled(t["function"]["name"])]
