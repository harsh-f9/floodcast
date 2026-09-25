"""Version stamp for /predict responses (migratable, Phase 05 part).

Stdlib-only. Delete file to remove feature. Wiring (one-spot, Phase 05 ship):
    from Flood_prediction.version_stamp import build_stamp
    return {**result, **build_stamp()}

Stamp: {model_version, db_date, generation_id}.
- model_version: sha1(model_config.json)[:8] + arch tag (stable, no torch).
- db_date: max gauge_state date if DB reachable, else None (lazy, never crashes).
- generation_id: uuid4 hex (per-response).
"""

import hashlib
import json
import os
import uuid

DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")
CONFIG_PATH = os.path.join(DEPLOY_DIR, "model_config.json")


def get_model_version() -> str:
    try:
        with open(CONFIG_PATH, "rb") as f:
            h = hashlib.sha1(f.read()).hexdigest()[:8]
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        arch = cfg.get("architecture", {})
        tag = f"{arch.get('input_size', 32)}d-{arch.get('hidden_size', 256)}h"
        return f"hybrid-lstm-xgb-{tag}-{h}"
    except Exception:
        return "hybrid-lstm-xgb-unknown"


def get_db_date() -> str | None:
    try:
        from Flood_prediction import database as db
    except ImportError:
        try:
            import database as db
        except ImportError:
            return None
    try:
        row = db.query_one("SELECT MAX(date) AS d FROM gauge_state")
        return row["d"] if row else None
    except Exception:
        return None


def build_stamp() -> dict:
    return {
        "model_version": get_model_version(),
        "db_date": get_db_date(),
        "generation_id": uuid.uuid4().hex[:12],
    }
