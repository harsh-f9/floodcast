"""Server-side district <-> station mapping for the chat agent.

Source of truth for districts: the enriched gauge JSON already shipped with the
repo (same file FloodDashboard reads). Station ids come from the SQLite DB
(station_static.station_name holds the gauge_id, e.g. 'hybas_...').

No duplication: this module only reads, never copies, those sources.
"""
import json
import os
from functools import lru_cache

_HERE = os.path.dirname(os.path.abspath(__file__))

# Repo root is two levels up from backend/chat_agent (backend/.. = repo root).
_CANDIDATES = [
    os.path.join(_HERE, "..", "..", "gauge_locations_enriched.json"),
    os.path.join(_HERE, "..", "..", "src", "data", "gauge_locations_enriched.json"),
]


def _mapping_path() -> str | None:
    for p in _CANDIDATES:
        if os.path.exists(p):
            return p
    return None


@lru_cache(maxsize=1)
def gauge_to_district() -> dict:
    """gauge_id -> {district, location_name, sub_district}."""
    path = _mapping_path()
    if not path:
        return {}
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    out = {}
    for r in rows:
        gid = r.get("gauge_id")
        if gid:
            out[gid] = {
                "district": r.get("district", ""),
                "location_name": r.get("location_name", ""),
                "sub_district": r.get("sub_district", ""),
            }
    return out


@lru_cache(maxsize=1)
def all_districts() -> list:
    return sorted({v["district"] for v in gauge_to_district().values() if v["district"]})


def _db():
    # Reuse the same import pattern as backend/main.py.
    try:
        import Flood_prediction.database as flood_db  # type: ignore
    except ImportError:
        import database as flood_db  # type: ignore
    return flood_db


def stations_for_district(district: str) -> list:
    """DB stations (station_id + thresholds) belonging to a district, ordered by id."""
    mapping = gauge_to_district()
    flood_db = _db()
    out = []
    for s in flood_db.get_all_stations():
        info = mapping.get(s.get("station_name", ""), {})
        if info.get("district") == district:
            out.append({**dict(s), **info})
    return out


def district_of_station(station: dict) -> str:
    return gauge_to_district().get(station.get("station_name", ""), {}).get("district", "")
