"""Chat-agent tools: thin wrappers over the existing prediction system.

Each tool mirrors an existing API route but runs in-process (no HTTP self-call):

  district_stations  <-  GET /stations + GET /api/districts (+ enriched mapping)
  station_history    <-  GET /station/{id}  (read-only, last 7 days or latest available)
  predict_district   <-  POST /predict       (anchor + horizon via predict_future_streamflow)

Heavy imports (prediction_service -> torch) are lazy so that importing this
module never loads the ML model. Caps keep chat requests production-safe.
"""
from datetime import date, timedelta, timezone

from . import district_map
from .log import event
from .schema import schema_prompt as _schema_prompt  # noqa: F401 (re-export for agent)
from .sql_exec import execute_sql

IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    """Current date in Asia/Kolkata (fixed +5:30 offset, no tz database needed)."""
    from datetime import datetime

    return datetime.now(IST).date()

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


def _forecast_one_station(s: dict, horizon_days: int, district: str = "") -> dict:
    """Shared per-station forecast core: past rows + trajectory + peak card."""
    flood_db = _db()
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
    past_peak = max([r["streamflow"] for r in past_rows] or [0.0])
    traj_peak = max([r["streamflow"] for r in future_rows] or [0.0])
    peak_flow = max([r["streamflow"] for r in past_rows + future_rows] or [0.0])
    peak_date = next(
        (r["date"] for r in (past_rows + future_rows) if r["streamflow"] == peak_flow),
        target.isoformat(),
    )
    event("predict.station", station_id=sid, district=district,
          anchor=_anchor.isoformat(), target=target.isoformat(),
          past_n=len(past_rows), past_peak=past_peak,
          past_peak_date=next((r["date"] for r in past_rows if r["streamflow"] == past_peak), ""),
          traj_n=len(future_rows), traj_peak=traj_peak,
          final_peak=peak_flow, final_peak_date=peak_date,
          severity=severity_of(peak_flow, s))
    return {
        "station_id": sid,
        "station_name": s.get("station_name", ""),
        "location_name": s.get("location_name", ""),
        "thresholds": thresholds_of(s),
        "peak_flow": peak_flow,
        "peak_date": peak_date,
        "severity": severity_of(peak_flow, s),
        "chart": past_rows + future_rows,
        "anchor": _anchor.isoformat(),
        "target": target.isoformat(),
    }


def predict_station(station_id: int, horizon_days: int = 7) -> dict:
    """Forecast for ONE gauge station (model run, 1-7 day horizon).

    Returns the same peak card predict_district produces per station,
    plus district/location resolution for the gauge.
    """
    horizon_days = max(MIN_HORIZON_DAYS, min(int(horizon_days), MAX_HORIZON_DAYS))
    flood_db = _db()
    station = flood_db.get_station(int(station_id))
    if not station:
        raise ValueError(f"Station {station_id} not found.")
    station = dict(station)
    info = district_map.gauge_to_district().get(station.get("station_name", ""), {})
    station = {**station, **info}
    district = info.get("district", "")
    card = _forecast_one_station(station, horizon_days, district)
    return {
        "district": district,
        "location_name": info.get("location_name", ""),
        "sub_district": info.get("sub_district", ""),
        "horizon_days": horizon_days,
        **card,
    }


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

    per_district = []
    for district in districts:
        stations = district_map.stations_for_district(district)
        if not stations:
            raise ValueError(
                f"Unknown district '{district}'. "
                f"Known districts include: {', '.join(district_map.all_districts()[:10])}…"
            )
        covered = stations[:MAX_STATIONS_PER_DISTRICT]
        station_results = [_forecast_one_station(s, horizon_days, district) for s in covered]
        try:
            from Flood_prediction.briefing import summarize_district  # type: ignore
        except ImportError:
            from briefing import summarize_district  # type: ignore
        # Briefing must peak over the SAME full window (past + forecast) as the
        # station cards above. briefing._peak_of only scans "trajectory", so the
        # full chart is passed as trajectory points — previously only forecast
        # rows were passed, which contradicted the cards whenever a past actual
        # exceeded the forecast peak (the Bijnor-212 class of failure).
        briefing_results = {
            r["station_id"]: {
                "trajectory": [
                    {"date": p["date"], "pred_raw_streamflow": p["streamflow"]}
                    for p in r["chart"]
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
        event("briefing.done", district=district,
              stations_covered=len(covered), paragraph=paragraph[:600])
        per_district.append({
            "district": district,
            "stations_total": len(stations),
            "stations_covered": len(covered),
            "truncated": len(stations) > len(covered),
            "briefing": paragraph,
            "stations": station_results,
        })
    return {"horizon_days": horizon_days, "results": per_district}


# ── Tool: district_rainfall (district aggregate, read-only) ───────────────

def district_rainfall(district: str, days: int = 7) -> dict:
    """Daily average rainfall across a district's stations (latest available window).

    Anchored at the latest date present in the district's rainfall records;
    stale_days = days between today (IST) and that anchor. Chart card carries
    unit "mm" and a label; station_id is -1 (aggregate, not a gauge).
    """
    from . import flags as _flags

    if not _flags.district_rainfall():
        raise ValueError("district_rainfall is disabled by feature flag.")
    days = max(1, min(int(days), MAX_HISTORY_DAYS))
    stations = district_map.stations_for_district(district)
    if not stations:
        raise ValueError(
            f"Unknown district '{district}'. "
            f"Known districts include: {', '.join(district_map.all_districts()[:10])}…")
    flood_db = _db()
    ids = [s["station_id"] for s in stations]
    placeholders = ",".join("?" * len(ids))
    anchor_row = flood_db.query_one(
        f"SELECT MAX(date) AS m FROM station_rainfall_history WHERE station_id IN ({placeholders})",
        ids,
    )
    anchor = anchor_row["m"] if anchor_row and anchor_row["m"] else today_ist().isoformat()
    start = (date.fromisoformat(anchor) - timedelta(days=days - 1)).isoformat()
    rows = flood_db.query(
        f"SELECT date, AVG(rainfall_mm) AS avg_rain, MAX(rainfall_mm) AS max_rain, "
        f"COUNT(*) AS n FROM station_rainfall_history "
        f"WHERE station_id IN ({placeholders}) AND date >= ? AND date <= ? "
        f"GROUP BY date ORDER BY date ASC",
        ids + [start, anchor],
    )
    daily = [{
        "date": r["date"],
        "avg_rainfall_mm": round(float(r["avg_rain"] or 0.0), 2),
        "max_rainfall_mm": round(float(r["max_rain"] or 0.0), 2),
        "stations_reporting": int(r["n"]),
    } for r in rows]
    stale_days = (today_ist() - date.fromisoformat(anchor)).days
    peak = max([d["avg_rainfall_mm"] for d in daily] or [0.0])
    return {
        "district": district,
        "unit": "mm",
        "anchor": anchor,
        "today_ist": today_ist().isoformat(),
        "stale_days": stale_days,
        "days_requested": days,
        "days_returned": len(daily),
        "stations_total": len(ids),
        "daily": daily,
        "chart": {
            "station_id": -1,
            "station_name": "",
            "district": district,
            "label": f"{district} district daily avg rainfall",
            "unit": "mm",
            "thresholds": {"watch": 0, "warning": 0, "danger": 0, "extreme": 0},
            "chart": [{"date": d["date"], "streamflow": d["avg_rainfall_mm"], "kind": "past"}
                      for d in daily],
            "severity": "",
            "peak_flow": peak,
            "peak_date": next((d["date"] for d in daily if d["avg_rainfall_mm"] == peak), ""),
        },
    }


# ── Tool: ensure_rainfall (live backfill → persist → re-read) ──────────────

RAINFALL_BACKFILL_CAP = 40  # max stations per direct call (HTTP budget)
RAINFALL_LOOKBACK_DAYS = 92  # Open-Meteo reliable past window
RAINFALL_LOOKAHEAD_DAYS = 7


def _fetch_rain_multi(coords: list, start: str, end: str) -> list:
    # Same Windows cp1252 guard as _predict_one: prediction_service prints
    # emoji status lines that crash non-UTF-8 consoles.
    import contextlib
    import io

    try:
        from Flood_prediction.prediction_service import fetch_rainfall_batch_multi  # type: ignore
    except ImportError:
        from prediction_service import fetch_rainfall_batch_multi  # type: ignore
    with contextlib.redirect_stdout(io.StringIO()):
        return fetch_rainfall_batch_multi(coords, start, end)


def ensure_rainfall(district: str | None = None, station_ids: list | None = None,
                    days: int = 7) -> dict:
    """Fetch MISSING recent rainfall from Open-Meteo (in-project API) and persist
    it to station_rainfall_history for future use. Read-only DB queries come first;
    call this only for date ranges with no stored rows.

    Only dates the API actually returns are inserted (INSERT OR IGNORE, so
    re-runs are free). Window is clamped to the reliable API range.
    """
    from . import flags as _flags
    from . import jobs as _jobs

    if not _flags.rainfall_backfill():
        raise ValueError("rainfall backfill is disabled by feature flag (read-only mode).")
    days = max(1, min(int(days), 30))
    flood_db = _db()
    stations = []
    if district:
        stations = district_map.stations_for_district(district)
        if not stations:
            raise ValueError(f"Unknown district '{district}'.")
    mapping = district_map.gauge_to_district()
    for sid in station_ids or []:
        st = flood_db.get_station(int(sid))
        if not st:
            raise ValueError(f"Station {sid} not found.")
        if all(s["station_id"] != int(sid) for s in stations):
            stations.append({**dict(st), **mapping.get(st.get("station_name", ""), {})})
    if not stations:
        raise ValueError("Backfill scope is empty: give a district or station_ids.")
    job_id = _jobs.current_job()
    if not job_id and len(stations) > RAINFALL_BACKFILL_CAP:
        raise ValueError(
            f"Scope has {len(stations)} stations; max {RAINFALL_BACKFILL_CAP} per direct call. "
            "Split by district or run as a background job.")
    today = today_ist()
    start = max(today - timedelta(days=RAINFALL_LOOKBACK_DAYS),
                today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()  # history only; forecast rain is fetched by the predict path
    coords = [{"station_id": s["station_id"], "latitude": s["latitude"],
               "longitude": s["longitude"]} for s in stations]
    if job_id:
        _jobs.set_progress(job_id, 0, len(coords), f"rainfall backfill {start}..{end}")
    fetched = _fetch_rain_multi(coords, start, end)
    inserted = 0
    for entry in fetched or []:
        sid = entry.get("station_id")
        daily = entry.get("daily") or {}
        dates = daily.get("time") or []
        rains = daily.get("precipitation_sum") or []
        for d, r in zip(dates, rains):
            try:
                flood_db.insert_rainfall(int(sid), str(d), float(r or 0.0))
                inserted += 1
            except (TypeError, ValueError):
                continue
    if job_id:
        _jobs.set_progress(job_id, len(coords), len(coords), "rainfall backfill done")
    event("rainfall.backfill", district=district or "",
          stations=len(coords), window=f"{start}..{end}", inserted=inserted)
    return {"district": district or "", "stations": len(coords),
            "window": {"start": start, "end": end}, "inserted": inserted}


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
            "Districts live in station_district.district (TEXT); "
            "DIST_SINK is km of river distance, never a district code."
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
    district_col = next((c for c in columns if str(c).lower() == "district"), None)
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
        sql_district = ""
        if district_col is not None:
            for r in rs:
                if r.get(district_col):
                    sql_district = str(r[district_col])
                    break
        charts.append({
            "station_id": sid,
            "station_name": station.get("station_name", ""),
            "district": sql_district or district_map.district_of_station(station),
            "label": "",
            "unit": "m³/s",
            "thresholds": thresholds_of(station),
            "chart": pts,
            "severity": severity_of(peak, station),
            "peak_flow": peak,
            "peak_date": next((p["date"] for p in pts if p["streamflow"] == peak), ""),
        })
    return charts

# ── Tool: sweep_stations (batch backfill: run model, save, rank) ──────────

SWEEP_SYNC_CAP = 40  # max stations per call outside a background job
SWEEP_TOP_N = 15


def _resolve_sweep_stations(districts=None, station_ids=None, all_stations=False) -> list:
    flood_db = _db()
    if all_stations:
        mapping = district_map.gauge_to_district()
        return [{**dict(s), **mapping.get(s.get("station_name", ""), {})}
                for s in flood_db.get_all_stations()]
    out, seen = [], set()
    for d in districts or []:
        found = district_map.stations_for_district(d)
        if not found:
            raise ValueError(
                f"Unknown district '{d}'. "
                f"Known districts include: {', '.join(district_map.all_districts()[:10])}…")
        for s in found:
            if s["station_id"] not in seen:
                seen.add(s["station_id"])
                out.append(s)
    mapping = district_map.gauge_to_district()
    for sid in station_ids or []:
        sid = int(sid)
        if sid in seen:
            continue
        st = flood_db.get_station(sid)
        if not st:
            raise ValueError(f"Station {sid} not found.")
        seen.add(sid)
        out.append({**dict(st), **mapping.get(st.get("station_name", ""), {})})
    return out


def sweep_stations(districts=None, station_ids=None, all_stations=False,
                   horizon_days: int = 7) -> dict:
    """Run the forecast model over many stations, SAVE results to gauge_state,
    and return ranked peaks. The backfill-then-read primitive for coverage
    questions (e.g. top-5 across UP for a date window).

    Per-station failures are isolated (collected, never abort the sweep).
    Outside a background job, capped at SWEEP_SYNC_CAP stations (HTTP budget);
    inside a job the full scope runs with progress updates.
    """
    from . import jobs as _jobs

    horizon_days = max(MIN_HORIZON_DAYS, min(int(horizon_days), MAX_HORIZON_DAYS))
    stations = _resolve_sweep_stations(districts, station_ids, all_stations)
    if not stations:
        raise ValueError("Sweep scope is empty: give districts, station_ids, or all_stations=true.")
    job_id = _jobs.current_job()
    if not job_id and len(stations) > SWEEP_SYNC_CAP:
        raise ValueError(
            f"Scope has {len(stations)} stations; max {SWEEP_SYNC_CAP} per direct call. "
            "Split by district, or run as a background job.")
    cards, failed = [], []
    total = len(stations)
    for i, s in enumerate(stations, 1):
        try:
            cards.append(_forecast_one_station(s, horizon_days,
                                               s.get("district", "")))
        except Exception as e:
            failed.append({"station_id": s.get("station_id"), "error": str(e)[:200]})
        if job_id and (i % 5 == 0 or i == total):
            _jobs.set_progress(job_id, i, total,
                               f"sweep {i}/{total} stations (horizon {horizon_days}d)")
    ranked = sorted(cards, key=lambda c: c.get("peak_flow", 0.0), reverse=True)
    event("sweep.done", scope={"districts": districts, "n_ids": len(station_ids or []),
                               "all": bool(all_stations)},
          swept=len(cards), failed=len(failed), horizon_days=horizon_days)
    return {
        "swept": len(cards),
        "failed": failed,
        "horizon_days": horizon_days,
        "top": [{
            "station_id": c["station_id"],
            "station_name": c.get("station_name", ""),
            "district": next((s.get("district", "") for s in stations
                              if s["station_id"] == c["station_id"]), ""),
            "peak_flow": c.get("peak_flow"),
            "peak_date": c.get("peak_date", ""),
            "severity": c.get("severity", ""),
        } for c in ranked[:SWEEP_TOP_N]],
    }


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
            "name": "predict_station",
            "description": (
                "Forecast streamflow for ONE gauge station id (model run, "
                "1-7 day horizon). Use when the user names a station id AND "
                "asks for forecast/predict/future/risk — NOT for past history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "station_id": {"type": "integer", "description": "Gauge station id."},
                    "horizon_days": {
                        "type": "integer",
                        "description": "Forecast horizon 1-7 days.",
                        "default": 7,
                    },
                },
                "required": ["station_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sweep_stations",
            "description": (
                "Batch backfill: run the forecast model over MANY stations "
                "(a district list, explicit station ids, or all_stations=true), "
                "SAVE each forecast to the database, and return ranked peaks. "
                "Use for coverage questions (top-N across stations, date windows "
                "with missing rows). After sweeping, run_sql to rank and "
                "station_history for winners' graphs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "districts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "District names to sweep.",
                    },
                    "station_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Explicit station ids to sweep.",
                    },
                    "all_stations": {
                        "type": "boolean",
                        "description": "Sweep all ~378 stations (long; background only).",
                    },
                    "horizon_days": {"type": "integer", "description": "1-7.", "default": 7},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "district_rainfall",
            "description": (
                "Daily average rainfall across a district's gauge stations "
                "(latest available window, up to 7 days). Use for 'rainfall "
                "history/rain over past days in <district>' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "District name."},
                    "days": {"type": "integer", "description": "Days 1-7.", "default": 7},
                },
                "required": ["district"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_rainfall",
            "description": (
                "Fetch MISSING recent rainfall from Open-Meteo and SAVE it to "
                "the database for future use. Call when stored rainfall ends "
                "before the requested window (stale anchor) and the user needs "
                "recent days. Then re-read with district_rainfall/station_history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "District name."},
                    "station_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Explicit station ids.",
                    },
                    "days": {"type": "integer", "description": "Lookback window 1-30.", "default": 7},
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
    "predict_station": predict_station,
    "sweep_stations": sweep_stations,
    "station_history": station_history,
    "district_rainfall": district_rainfall,
    "ensure_rainfall": ensure_rainfall,
    "district_stations": district_stations,
    "describe_tables": describe_tables,
    "run_sql": run_sql,
}


def run_tool(name: str, args: dict) -> dict:
    import logging as _logging
    import time as _time

    from . import flags as _flags

    fn = _DISPATCH.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool '{name}'.")
    if not _flags.tool_enabled(name):
        raise ValueError(f"Tool '{name}' is disabled by feature flag.")
    args = dict(args or {})
    if name in ("station_history", "predict_station") and "station_id" in args:
        args["station_id"] = int(args["station_id"])
    if name in ("predict_district", "predict_station", "sweep_stations") and "horizon_days" in args:
        args["horizon_days"] = int(args["horizon_days"])
    if name == "sweep_stations" and "station_ids" in args and args["station_ids"] is not None:
        args["station_ids"] = [int(x) for x in args["station_ids"]]
    if name == "sweep_stations" and "all_stations" in args:
        args["all_stations"] = bool(args["all_stations"])
    safe_args = {k: (str(v)[:200] if k == "sql" else v) for k, v in args.items()}
    event("tool.start", tool=name, args=safe_args)
    t0 = _time.monotonic()
    try:
        out = fn(**{k: v for k, v in args.items() if v is not None} if name != "district_stations" else {"district": args.get("district")})
    except Exception as e:
        event("tool.done", tool=name, ok=False, latency_ms=round((_time.monotonic() - t0) * 1000),
              error=str(e)[:300], level=_logging.WARNING)
        raise
    latency_ms = round((_time.monotonic() - t0) * 1000)
    event("tool.done", tool=name, ok=not (isinstance(out, dict) and out.get("ok") is False),
          latency_ms=latency_ms, stats=_result_stats(name, out))
    return out


def _result_stats(name: str, out) -> dict:
    try:
        if not isinstance(out, dict):
            return {}
        if name == "predict_district":
            res = out.get("results", []) or []
            return {"districts": len(res),
                    "stations": sum(len(d.get("stations", [])) for d in res),
                    "peaks": [(s["station_id"], s.get("peak_flow"), s.get("peak_date"))
                              for d in res for s in d.get("stations", [])][:8]}
        if name == "station_history":
            hist = out.get("history", []) or []
            return {"rows": len(hist),
                    "range": [hist[0]["date"], hist[-1]["date"]] if hist else []}
        if name == "predict_station":
            return {"station_id": out.get("station_id"),
                    "peak": out.get("peak_flow"), "peak_date": out.get("peak_date"),
                    "severity": out.get("severity", ""),
                    "chart_points": len(out.get("chart", []) or [])}
        if name == "sweep_stations":
            return {"swept": out.get("swept", 0), "failed_n": len(out.get("failed", [])),
                    "top_n": len(out.get("top", []))}
        if name == "district_rainfall":
            return {"district": out.get("district"), "anchor": out.get("anchor"),
                    "stale_days": out.get("stale_days", 0),
                    "days_returned": out.get("days_returned", 0)}
        if name == "ensure_rainfall":
            return {"stations": out.get("stations", 0),
                    "window": out.get("window", {}),
                    "inserted": out.get("inserted", 0)}
        if name == "district_stations":
            return {"count": out.get("count", 0)}
        if name == "run_sql":
            return {"ok": out.get("ok"), "row_count": out.get("row_count", 0),
                    "truncated": out.get("truncated", False),
                    "error": str(out.get("error", ""))[:200]}
        if name == "describe_tables":
            return {"tables": len(out.get("tables", []))}
    except Exception:
        pass
    return {}
