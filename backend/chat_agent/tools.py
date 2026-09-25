"""Chat-agent tools: thin wrappers over the existing prediction system.

Each tool mirrors an existing API route but runs in-process (no HTTP self-call):

  district_stations  <-  GET /stations + GET /api/districts (+ enriched mapping)
  station_history    <-  GET /station/{id}  (read-only, last 7 days or latest available)
  predict_district   <-  POST /predict       (anchor + horizon via predict_future_streamflow)

Heavy imports (prediction_service -> torch) are lazy so that importing this
module never loads the ML model. Caps keep chat requests production-safe.
"""
from datetime import date, timedelta

from . import district_map
from .schema import schema_prompt as _schema_prompt  # noqa: F401 (re-export for agent)
from .sql_exec import execute_sql

MAX_DISTRICTS_PER_PREDICT = 2
MAX_STATIONS_PER_DISTRICT = 6
MAX_HISTORY_DAYS = 7
MIN_HORIZON_DAYS = 1
MAX_HORIZON_DAYS = 7

FALLBACK_REPLY = (
    "I can't answer that — I can only show flood predictions and station "
    "history. Try e.g. 'Predict Bijnor' or 'History of station 0'."
)


def _db():
    try:
        import Flood_prediction.database as flood_db  # type: ignore
    except ImportError:
        import database as flood_db  # type: ignore
    return flood_db


def severity_of(flow: float, station: dict) -> str:
    try:
        if flow < station["rp_2"]:
            return "NORMAL"
        if flow < station["rp_5"]:
            return "WATCH"
        if flow < station["rp_15"]:
            return "WARNING"
        if flow < station["rp_20"]:
            return "DANGER"
        return "EXTREME"
    except (KeyError, TypeError):
        return "UNKNOWN"


def thresholds_of(station: dict) -> dict:
    return {
        "watch": station.get("rp_2", 0) or 0,
        "warning": station.get("rp_5", 0) or 0,
        "danger": station.get("rp_15", 0) or 0,
        "extreme": station.get("rp_20", 0) or 0,
    }


# ── Tool 1: district_stations (cheap, read-only) ──────────────────────────

def district_stations(district: str | None = None) -> dict:
    """List stations, optionally filtered to one district, with RP thresholds."""
    flood_db = _db()
    if district:
        stations = district_map.stations_for_district(district)
        if not stations:
            known = district_map.all_districts()
            raise ValueError(
                f"Unknown district '{district}'. "
                f"Known districts include: {', '.join(known[:10])}… ({len(known)} total). "
                "Use district_stations with no arguments to list counts."
            )
    else:
        mapping = district_map.gauge_to_district()
        stations = []
        for s in flood_db.get_all_stations():
            stations.append({**dict(s), **mapping.get(s.get("station_name", ""), {})})
    return {
        "district": district or "All Districts",
        "count": len(stations),
        "stations": [
            {
                "station_id": s["station_id"],
                "station_name": s.get("station_name", ""),
                "district": s.get("district", ""),
                "location_name": s.get("location_name", ""),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
                "thresholds": thresholds_of(s),
            }
            for s in stations
        ],
    }


# ── Tool 2: station_history (cheap, read-only, station-level, ≤7 days) ────

def station_history(station_id: int, days: int = MAX_HISTORY_DAYS) -> dict:
    """Latest available streamflow + rainfall rows for one station (past 7 days)."""
    days = max(1, min(int(days), MAX_HISTORY_DAYS))
    flood_db = _db()
    station = flood_db.get_station(int(station_id))
    if not station:
        raise ValueError(f"Station {station_id} not found.")
    station = dict(station)
    flows = flood_db.query(
        "SELECT date, raw_streamflow FROM gauge_state "
        "WHERE station_id = ? ORDER BY date DESC LIMIT ?",
        [station["station_id"], days],
    )
    rows = []
    for r in reversed(flows):  # chronological for charts
        rain = flood_db.get_rainfall_for_date(station["station_id"], r["date"])
        rows.append({
            "date": r["date"],
            "streamflow": round(float(r["raw_streamflow"]), 1),
            "rainfall_mm": round(float(rain or 0.0), 2),
            "severity": severity_of(float(r["raw_streamflow"]), station),
            "kind": "past",
        })
    return {
        "station_id": station["station_id"],
        "station_name": station.get("station_name", ""),
        "district": district_map.district_of_station(station),
        "thresholds": thresholds_of(station),
        "days_requested": days,
        "days_returned": len(rows),
        "history": rows,
        "chart": [
            {"date": r["date"], "streamflow": r["streamflow"], "kind": "past"}
            for r in rows
        ],
    }


# ── Tool 3: predict_district (model runs, capped) ─────────────────────────

def _anchor_and_target(station_id: int, horizon_days: int):
    flood_db = _db()
    latest = flood_db.query(
        "SELECT date FROM gauge_state WHERE station_id = ? ORDER BY date DESC LIMIT 1",
        [int(station_id)],
    )
    anchor = date.fromisoformat(latest[0]["date"]) if latest else date.today()
    horizon_days = max(MIN_HORIZON_DAYS, min(int(horizon_days), MAX_HORIZON_DAYS))
    return anchor, anchor + timedelta(days=horizon_days)


def _predict_one(station_id: int, target) -> dict:
    # prediction_service prints emoji status lines; Windows consoles (cp1252)
    # cannot encode them and would crash the request. Silence stdout locally.
    import contextlib
    import io

    try:
        from Flood_prediction.prediction_service import predict_future_streamflow  # type: ignore
    except ImportError:
        from prediction_service import predict_future_streamflow  # type: ignore
    with contextlib.redirect_stdout(io.StringIO()):
        return predict_future_streamflow(int(station_id), target)


def predict_district(districts: list, horizon_days: int = 7) -> dict:
    """7-day forecast per station for up to 2 districts (≤6 stations each).

    Returns Recharts-ready chart arrays: 6 past rows + future trajectory.
    """
    if isinstance(districts, str):
        districts = [districts]
    districts = [d for d in districts if d]
    if not districts:
        raise ValueError("Provide at least one district name.")
    if len(districts) > MAX_DISTRICTS_PER_PREDICT:
        raise ValueError(
            f"Too many districts ({len(districts)}). Max {MAX_DISTRICTS_PER_PREDICT} "
            "per request — run one district at a time for big areas."
        )
    horizon_days = max(MIN_HORIZON_DAYS, min(int(horizon_days), MAX_HORIZON_DAYS))
    flood_db = _db()

    per_district = []
    for district in districts:
        stations = district_map.stations_for_district(district)
        if not stations:
            raise ValueError(
                f"Unknown district '{district}'. "
                f"Known districts include: {', '.join(district_map.all_districts()[:10])}…"
            )
        covered = stations[:MAX_STATIONS_PER_DISTRICT]
        station_results = []
        for s in covered:
            sid = s["station_id"]
            _anchor, target = _anchor_and_target(sid, horizon_days)
            past = flood_db.query(
                "SELECT date, raw_streamflow FROM gauge_state "
                "WHERE station_id = ? ORDER BY date DESC LIMIT 6",
                [sid],
            )
            past_rows = [
                {"date": r["date"], "streamflow": round(float(r["raw_streamflow"]), 1), "kind": "past"}
                for r in reversed(past)
            ]
            traj_out = _predict_one(sid, target)
            traj = traj_out.get("trajectory", []) or []
            future_rows = [
                {"date": t["date"], "streamflow": round(float(t["pred_raw_streamflow"]), 1), "kind": "forecast"}
                for t in traj
            ]
            peak_flow = max([r["streamflow"] for r in past_rows + future_rows] or [0.0])
            peak_date = next(
                (r["date"] for r in (past_rows + future_rows) if r["streamflow"] == peak_flow),
                target.isoformat(),
            )
            station_results.append({
                "station_id": sid,
                "station_name": s.get("station_name", ""),
                "location_name": s.get("location_name", ""),
                "thresholds": thresholds_of(s),
                "peak_flow": peak_flow,
                "peak_date": peak_date,
                "severity": severity_of(peak_flow, s),
                "chart": past_rows + future_rows,
            })
        try:
            from Flood_prediction.briefing import summarize_district  # type: ignore
        except ImportError:
            from briefing import summarize_district  # type: ignore
        briefing_results = {
            r["station_id"]: {
                "trajectory": [
                    {"date": p["date"], "pred_raw_streamflow": p["streamflow"]}
                    for p in r["chart"] if p["kind"] == "forecast"
                ],
                "pred_raw_streamflow": r["peak_flow"],
                "date": r["peak_date"],
            }
            for r in station_results
        }
        briefing_meta = {
            r["station_id"]: {
                "station_name": r["station_name"],
                "district": district,
                "rp_2": r["thresholds"]["watch"],
                "rp_5": r["thresholds"]["warning"],
                "rp_15": r["thresholds"]["danger"],
                "rp_20": r["thresholds"]["extreme"],
            }
            for r in station_results
        }
        paragraph = summarize_district(district, briefing_results, briefing_meta)["paragraph"]
        per_district.append({
            "district": district,
            "stations_total": len(stations),
            "stations_covered": len(covered),
            "truncated": len(stations) > len(covered),
            "briefing": paragraph,
            "stations": station_results,
        })
    return {"horizon_days": horizon_days, "results": per_district}


# ── OpenAI-compatible schemas (native tool calling) + dispatcher ──────────

def describe_tables() -> dict:
    """Schema catalog for the SQL surface (discover step, no DB hit)."""
    from .schema import CATALOG

    return {
        "dialect": "sqlite",
        "tables": [
            {"name": t, "description": m["description"], "columns": sorted(m["columns"].keys())}
            for t, m in CATALOG.items()
        ],
        "notes": (
            "Join on station_id. gauge_state.date is TEXT YYYY-MM-DD. "
            "District names are NOT in the database."
        ),
    }


def run_sql(sql: str) -> dict:
    """Run a read-only SELECT through the guard + read-only executor.

    Returns {ok, columns, rows, row_count, truncated, sql, error}.
    Repairs: on ok=false, rewrite the SQL using the error and retry.
    """
    return execute_sql(sql)


CANNED_TOP_FLOW = (
    "SELECT s.station_id, MAX(g.raw_streamflow) AS peak "
    "FROM station_static s JOIN gauge_state g ON g.station_id = s.station_id "
    "GROUP BY s.station_id ORDER BY peak DESC LIMIT 5"
)
CANNED_MAX_RP = (
    "SELECT station_id, station_name, rp_2, rp_5, rp_15, rp_20 "
    "FROM station_static ORDER BY rp_20 DESC LIMIT 5"
)


def charts_from_rows(rows: list, columns: list) -> list:
    """Build chart cards from arbitrary SQL rows (station_id + date + flow)."""
    if not rows:
        return []
    lower = [str(c).lower() for c in columns]
    if "station_id" not in lower:
        return []
    date_col = next((c for c in columns if str(c).lower() in ("date", "peak_date", "day")), None)
    flow_col = next(
        (c for c in columns
         if str(c).lower() in ("raw_streamflow", "peak", "streamflow", "flow", "rainfall_mm")),
        None,
    )
    if date_col is None or flow_col is None:
        return []
    flood_db = _db()
    grouped: dict = {}
    for r in rows:
        try:
            sid = int(r.get("station_id"))
            grouped.setdefault(sid, []).append(r)
        except (TypeError, ValueError):
            continue
    charts = []
    for sid, rs in grouped.items():
        station = flood_db.get_station(sid)
        if not station:
            continue
        station = dict(station)
        pts = []
        for r in rs:
            try:
                pts.append({
                    "date": str(r.get(date_col)),
                    "streamflow": round(float(r.get(flow_col)), 1),
                    "kind": "past",
                })
            except (TypeError, ValueError):
                continue
        pts.sort(key=lambda p: p["date"])
        peak = max([p["streamflow"] for p in pts] or [0.0])
        charts.append({
            "station_id": sid,
            "station_name": station.get("station_name", ""),
            "district": district_map.district_of_station(station),
            "thresholds": thresholds_of(station),
            "chart": pts,
            "severity": severity_of(peak, station),
            "peak_flow": peak,
            "peak_date": next((p["date"] for p in pts if p["streamflow"] == peak), ""),
        })
    return charts

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "predict_district",
            "description": (
                "Forecast streamflow for districts of Uttar Pradesh. "
                "Use when the user asks for predictions, forecast, risk or "
                "report for one or more districts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "districts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "District names, e.g. [\"Bijnor\"]. Max 2 per call.",
                    },
                    "horizon_days": {
                        "type": "integer",
                        "description": "Forecast horizon 1-7 days.",
                        "default": 7,
                    },
                },
                "required": ["districts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "station_history",
            "description": (
                "Past streamflow and rainfall for ONE gauge station "
                "(latest available, up to 7 days). Use for 'history', "
                "'past', 'previous dates' or 'old streamflow' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station_id": {"type": "integer", "description": "Gauge station id."},
                    "days": {"type": "integer", "description": "Days 1-7.", "default": 7},
                },
                "required": ["station_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "district_stations",
            "description": (
                "List gauge stations and their risk thresholds, optionally "
                "filtered to one district. Use to find station ids or explore "
                "which gauges a district has."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {
                        "type": "string",
                        "description": "District name. Omit to list all stations.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_tables",
            "description": (
                "Re-read the database schema (tables, columns, meanings). "
                "Call first when unsure which table holds an answer."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Run a read-only SQLite SELECT for cross-station analytics "
                "(top-N, max/min, aggregates, history ranges). "
                "Only allowlisted tables/columns, explicit columns (no *), "
                "LIMIT <= 100. On error, rewrite and retry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Single SELECT statement.",
                    },
                },
                "required": ["sql"],
            },
        },
    },
]

_DISPATCH = {
    "predict_district": predict_district,
    "station_history": station_history,
    "district_stations": district_stations,
    "describe_tables": describe_tables,
    "run_sql": run_sql,
}


def run_tool(name: str, args: dict) -> dict:
    fn = _DISPATCH.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool '{name}'.")
    args = dict(args or {})
    if name == "station_history" and "station_id" in args:
        args["station_id"] = int(args["station_id"])
    if name == "predict_district" and "horizon_days" in args:
        args["horizon_days"] = int(args["horizon_days"])
    return fn(**{k: v for k, v in args.items() if v is not None} if name != "district_stations" else {"district": args.get("district")})
