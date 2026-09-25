"""Kill switch for the flood chat agent — edit this file to disable the feature.

    CHAT_ENABLED = False   # chat UI hides, POST /api/chat returns 503

Env override (no code change):  CHAT_ENABLED=0
"""
import os

CHAT_ENABLED = True


def is_enabled() -> bool:
    if os.environ.get("CHAT_ENABLED", "").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(CHAT_ENABLED)
