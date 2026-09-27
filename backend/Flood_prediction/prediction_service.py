"""
Core prediction service for the Flood Prediction system.
Contains rainfall fetching, feature window construction, and prediction orchestration.

The StreamflowPredictor is instantiated ONCE at module level and reused forever.
"""

import os
import sys
import numpy as np
import pandas as pd
import requests
from datetime import date, datetime, timedelta, timezone
import time

# Add deploy directory to path so predictor.py can import flood_lstm
DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")
sys.path.insert(0, DEPLOY_DIR)

from predictor import StreamflowPredictor

# ── Module-level singleton — loaded once, reused forever ──────────────
_predictor: StreamflowPredictor | None = None


def get_predictor() -> StreamflowPredictor:
    """Get or create the singleton StreamflowPredictor."""
    global _predictor
    if _predictor is None:
        print("🔄 Loading StreamflowPredictor...")
        _predictor = StreamflowPredictor(DEPLOY_DIR + "/")
    return _predictor


# ── Exact scaler column lists (from training code) ────────────────────
# These MUST match what the .pkl scalers were fit_transform()-ed on.

YJ_RAW_COLS = [
    'UP_AREA', 'rain_basin_size_interaction', 'uparea_upstream_rain_interaction',
    'rain_slope_interaction', 'rain_urban_interaction', 'rain_monthly_swc_interaction',
    'upstream_rain_mean', 'weighted_upstream_rain'
]

MM_COLS = [
    'soil_saturation_score', 'antecedent_saturation_interaction',
    'antecedent_rain_3d_sum', 'antecedent_rain_7d_sum', 'antecedent_rain_15d_sum',
    'antecedent_rain_30d_sum', 'antecedent_rain_ewm', 'antecedent_rain_3d_mean',
    'antecedent_rain_7d_mean', 'antecedent_rain_15d_mean', 'antecedent_rain_30d_mean',
    'antecedent_rain_60d', 'antecedent_rain_30d_sum_log', 'monsoon_cumulative_rain'
]

STANDARD_FEATURE_COLS = [
    'upstream_lag1_streamflow_log_delta', 'upstream_lag2_streamflow_log_delta',
    'rainfall_mm_log_delta', 'upstream_weighted_streamflow_log_delta',
    'slp_dg', 'slp_dg_uav', 'DIST_SINK', 'for_pc', 'urb_pc', 'attenuation_factor',
    'flow_velocity_km_per_day', 'upstream_lag1_days', 'upstream_lag2_days',
    'upstream_rain_lagged_dist_sink', 'estimated_return_period', 'flow_rp15_ratio'
]


def preprocess_window(df_window: pd.DataFrame, predictor: StreamflowPredictor):
    """
    Apply the exact same 3-step scaling pipeline used during training.
    Uses the scaler objects from the predictor but with the CORRECT column lists
    (which may differ from model_config.json due to config drift).

    Returns:
        x_dynamic : np.ndarray (SEQ_LEN, 32) — for LSTM
        x_flat    : np.ndarray (42,)          — for XGBoost (last row)
    """
    df = df_window.copy()

    # Step 1: Yeo-Johnson on raw interaction/area cols → rename to _yj
    df[YJ_RAW_COLS] = predictor.yj_transformer.transform(df[YJ_RAW_COLS])
    rename_map = {col: f"{col}_yj" for col in YJ_RAW_COLS}
    df = df.rename(columns=rename_map)

    # Step 2: MinMax scale capacity / antecedent cols (all 14 the scaler expects)
    df[MM_COLS] = predictor.mm_scaler.transform(df[MM_COLS])

    # Step 3: Standard scale delta / static / routing cols (all 16 the scaler expects)
    df[STANDARD_FEATURE_COLS] = predictor.feature_scaler.transform(df[STANDARD_FEATURE_COLS])

    # Step 4: Extract arrays in exact column order from config
    dynamic_cols = predictor.dynamic_cols
    flat_cols    = predictor.flat_cols

    x_dynamic = df[dynamic_cols].values.astype(np.float32)       # (15, 32)
    x_flat    = df[flat_cols].iloc[-1].values.astype(np.float32)  # (42,)

    return x_dynamic, x_flat


# ── Rainfall fetching ─────────────────────────────────────────────────

def fetch_rainfall_mm(lat: float, lon: float, date_str: str) -> float:
    """Fetch rainfall for a single day from Open-Meteo."""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum",
            "start_date": date_str,
            "end_date": date_str,
            "timezone": "Asia/Kolkata"
        }, timeout=10)
        r.raise_for_status()
        val = r.json()["daily"]["precipitation_sum"][0]
        return float(val) if val is not None else 0.0
    except Exception as e:
        print(f"⚠️  Rainfall fetch failed for ({lat},{lon}) on {date_str}: {e}")
        return 0.0


def _fetch_live_rainfall_or_raise(lat: float, lon: float, date_str: str) -> float:
    """Single-day live rainfall fetch that RAISES on any failure.

    Unlike fetch_rainfall_mm (which swallows errors into 0.0), this lets the
    per-date resolver distinguish genuine 0.0mm from a failed fetch so the
    fallback chain (batch -> db -> flagged fallback-zero) can engage.
    """
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "Asia/Kolkata"
    }, timeout=10)
    r.raise_for_status()
    val = r.json()["daily"]["precipitation_sum"][0]
    return float(val) if val is not None else 0.0


def fetch_rainfall_batch(lat: float, lon: float, start_date: str, end_date: str) -> dict[str, float]:
    """
    Fetch rainfall for a date range from Open-Meteo (one API call).
    Returns dict: {date_str: rainfall_mm}
    """
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum",
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "Asia/Kolkata"
        }, timeout=30)
        r.raise_for_status()
        data = r.json()["daily"]
        dates = data["time"]
        precips = data["precipitation_sum"]
        result = {}
        for d, p in zip(dates, precips):
            result[d] = float(p) if p is not None else 0.0
        return result
    except Exception as e:
        print(f"⚠️  Batch rainfall fetch failed for ({lat},{lon}): {e}")
        return {}


def fetch_rainfall_batch_multi(stations_coords: list[dict], start_date: str, end_date: str) -> list[dict]:
    """
    Fetch rainfall for multiple stations in parallel using Open-Meteo's location array feature.
    Chunked into batches of 50 to avoid HTTP 414 Request-URI Too Large errors.
    """
    if not stations_coords:
        return []
        
    chunk_size = 50
    output = []
    
    for i in range(0, len(stations_coords), chunk_size):
        chunk = stations_coords[i:i + chunk_size]
        
        max_retries = 5
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                lats = [s["latitude"] for s in chunk]
                lons = [s["longitude"] for s in chunk]
                
                r = requests.get("https://api.open-meteo.com/v1/forecast", params={
                    "latitude": lats,
                    "longitude": lons,
                    "daily": "precipitation_sum",
                    "start_date": start_date,
                    "end_date": end_date,
                    "timezone": "Asia/Kolkata"
                }, timeout=60)
                
                if r.status_code == 429:
                    raise requests.exceptions.RequestException("429 Too Many Requests")
                r.raise_for_status()
                
                res_list = r.json()
                if isinstance(res_list, dict):
                    res_list = [res_list]
                    
                for station, data in zip(chunk, res_list):
                    daily_data = data.get("daily", {})
                    output.append({
                        "station_id": station["station_id"],
                        "daily": daily_data
                    })
                    
                # Success - break out of the retry loop
                break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️  Chunk batch fetch failed (indices {i} to {i+chunk_size}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"❌  Chunk batch fetch completely failed after {max_retries} attempts: {e}")
            
        # Add a small delay between successful chunks as well
        time.sleep(3)
            
    return output


# ── Return period computation ─────────────────────────────────────────

def clamp_flow(v: float) -> float:
    """Physical guard: streamflow can't be negative (pipeline Phase-7 reconstruct uses max(0)).
    Predictor (frozen contract) may overshoot on anchor discontinuities; clamp here so
    chained state never carries unphysical values. Returns 0.0 for NaN."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f or f < 0.0:  # NaN or negative
        return 0.0
    return f


def compute_return_period(streamflow: float, rp_2: float, rp_5: float, rp_15: float) -> float:
    """Compute estimated return period from streamflow and return period thresholds."""
    if streamflow < rp_2:
        return streamflow / (rp_2 + 0.1)
    elif streamflow < rp_5:
        return 2 + (streamflow - rp_2) / (rp_2 * 0.33)
    else:
        return 5 + (streamflow - rp_5) / (rp_5 * 0.25)


# ── Feature window construction ──────────────────────────────────────

def build_feature_window(
    station: dict,
    rain_series: pd.Series,
    last_raw: float,
    prev_raw: float,
    target_date: date,
) -> pd.DataFrame:
    """
    Build the 15-row feature window DataFrame required by StreamflowPredictor.

    Args:
        station: dict from station_static table
        rain_series: pd.Series with DatetimeIndex, values = rainfall_mm
        last_raw: most recent raw streamflow
        prev_raw: second most recent raw streamflow
        target_date: the date we're predicting for
    """
    window_rows = []

    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        row_rain = rain_series.get(pd.Timestamp(row_date), 0.0)

        rain_slice = rain_series[rain_series.index <= pd.Timestamp(row_date)]
        r3  = float(rain_slice.tail(3).sum())
        r7  = float(rain_slice.tail(7).sum())
        r15 = float(rain_slice.tail(15).sum())
        r30 = float(rain_slice.tail(30).sum())
        r60 = float(rain_slice.tail(60).sum())
        ewm = float(rain_slice.ewm(span=30).mean().iloc[-1]) if len(rain_slice) else 0.0
        r30_log = np.log1p(r30)

        m   = row_date.month
        doy = row_date.timetuple().tm_yday

        june1 = date(row_date.year, 6, 1)
        if row_date < june1:
            june1 = date(row_date.year - 1, 6, 1)
        monsoon_rain = float(
            rain_series[rain_series.index >= pd.Timestamp(june1)].sum()
        )

        ss_score = r30 / (station["max_30d_rain"] + 1e-6)
        erp = compute_return_period(
            last_raw, station["rp_2"], station["rp_5"], station["rp_15"]
        )

        prev_day_rain = rain_series.get(
            pd.Timestamp(row_date - timedelta(1)), 0.0
        )

        window_rows.append({
            # Raw rain features
            "rainfall_mm":                        row_rain,
            "rainfall_mm_log":                    np.log1p(row_rain),
            "rainfall_mm_log_delta":              np.log1p(row_rain) - np.log1p(prev_day_rain),
            # Rolling windows — sums
            "antecedent_rain_3d_sum":             r3,
            "antecedent_rain_7d_sum":             r7,
            "antecedent_rain_15d_sum":            r15,
            "antecedent_rain_30d_sum":            r30,
            "antecedent_rain_60d":                r60,
            "antecedent_rain_ewm":                ewm,
            "antecedent_rain_30d_sum_log":        r30_log,
            "monsoon_cumulative_rain":            monsoon_rain,
            # Rolling windows — means (required by mm_scaler)
            "antecedent_rain_3d_mean":            r3 / 3.0,
            "antecedent_rain_7d_mean":            r7 / 7.0,
            "antecedent_rain_15d_mean":           r15 / 15.0,
            "antecedent_rain_30d_mean":           r30 / 30.0,
            # Seasonal
            "monsoon_intensity":                  1 if m in [6, 7, 8, 9, 10] else 0,
            "is_post_monsoon_saturated":          1 if m in [10, 11] else 0,
            "month_sin":                          np.sin(2 * np.pi * (m - 1) / 12),
            "month_cos":                          np.cos(2 * np.pi * (m - 1) / 12),
            "doy_sin":                            np.sin(2 * np.pi * doy / 365),
            "doy_cos":                            np.cos(2 * np.pi * doy / 365),
            # Saturation
            "soil_saturation_score":              ss_score,
            "antecedent_saturation_interaction":  ss_score * r7,
            # Flow features
            "flow_rate_of_change":                (last_raw - prev_raw) / (prev_raw + 1e-6),
            "estimated_return_period":            erp,
            "flow_rp15_ratio":                    last_raw / (station["rp_15"] + 1e-6),
            # Upstream approximated from local rainfall
            "upstream_rain_mean":                 row_rain,
            "weighted_upstream_rain":             row_rain,
            "upstream_rain_lagged_dist_sink":     row_rain * (station["DIST_SINK"] / (station["flow_velocity_km_per_day"] + 1e-6)),
            # Static × rain interactions
            "rain_urban_interaction":             row_rain * station["urb_pc"],
            "rain_slope_interaction":             row_rain * station["slp_dg"],
            "rain_basin_size_interaction":        row_rain * station["UP_AREA"],
            "rain_monthly_swc_interaction":       row_rain * r30,
            "uparea_upstream_rain_interaction":   station["UP_AREA"] * row_rain,
            # Static features
            "UP_AREA":                            station["UP_AREA"],
            "DIST_SINK":                          station["DIST_SINK"],
            "slp_dg":                             station["slp_dg"],
            "slp_dg_uav":                         station["slp_dg_uav"],
            "for_pc":                             station["for_pc"],
            "urb_pc":                             station["urb_pc"],
            "attenuation_factor":                 station["attenuation_factor"],
            "flow_velocity_km_per_day":           station["flow_velocity_km_per_day"],
            "upstream_lag1_days":                  station["upstream_lag1_days"],
            "upstream_lag2_days":                  station["upstream_lag2_days"],
            # Zeroed — upstream gauges unavailable, NSE impact = 0.0000
            "upstream_weighted_streamflow_log":        0.0,
            "upstream_weighted_streamflow_log_delta":  0.0,
            "upstream_lag1_streamflow_log_delta":      0.0,
            "upstream_lag2_streamflow_log_delta":      0.0,
        })

    return pd.DataFrame(window_rows)


# ── Backfill guarantee: anchor → today, per-date live dynamic features ───
# Phase 07-prediction-backfill-guarantee. Every prediction entry point (agent
# tools AND user POST /predict, both of which funnel through the two public
# functions below) must first compute the anchor->today gap date-by-date with
# live rainfall + feature window + chained model state before answering the
# requested target date.

IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> date:
    """Portable 'current date': Asia/Kolkata wall-clock wherever this runs.

    Prefers the chat-agent clock (honours validated client_today override);
    falls back to a fixed +5:30 offset (no tz database needed, works on any
    Indian laptop and on Render); last resort is the system date.
    """
    try:
        try:
            from chat_agent.clock import today_ist as _tist
        except ImportError:
            from backend.chat_agent.clock import today_ist as _tist
        return _tist()
    except Exception:
        pass
    try:
        return datetime.now(IST_OFFSET).date()
    except Exception:
        return date.today()


def _resolve_rainfall_for_date(
    station: dict,
    date_str: str,
    client_rainfall: dict[str, float] | None = None,
    batch_state: dict | None = None,
) -> tuple[float, str]:
    """Resolve rainfall for ONE date. Always attempts live first.

    Order: client override -> live single-day Open-Meteo -> bulk batch cache
    (fetched lazily once, only after a live failure) -> stored DB row ->
    fallback-zero (explicitly flagged, never silent).

    batch_state is a mutable dict owned by the gap loop with keys:
      cache: dict|None (bulk fallback values), live_disabled: bool (429
      circuit breaker — stop hammering live for the rest of this call),
      end: str|None (range end for the lazy bulk fetch).

    Returns (rainfall_mm, source) where source is one of
    client|live|batch|db|fallback-zero.
    """
    if client_rainfall and date_str in client_rainfall:
        try:
            return float(client_rainfall[date_str]), "client"
        except (TypeError, ValueError):
            pass

    if batch_state is None:
        batch_state = {}

    if not batch_state.get("live_disabled"):
        try:
            val = _fetch_live_rainfall_or_raise(
                station["latitude"], station["longitude"], date_str
            )
            return val, "live"
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg:
                # Circuit breaker: one 429 disables further live attempts
                # for the rest of this gap loop (avoids an IP ban).
                batch_state["live_disabled"] = True
            # Lazy bulk fallback: one range call covers the remaining dates.
            if batch_state.get("cache") is None and batch_state.get("end"):
                try:
                    batch_state["cache"] = fetch_rainfall_batch(
                        station["latitude"], station["longitude"],
                        date_str, batch_state["end"],
                    ) or {}
                except Exception:
                    batch_state["cache"] = {}

    cache = batch_state.get("cache") or {}
    if date_str in cache:
        try:
            return float(cache[date_str]), "batch"
        except (TypeError, ValueError):
            pass

    try:
        from database import get_rainfall_for_date
        db_val = get_rainfall_for_date(station["station_id"], date_str)
    except Exception:
        db_val = None
    if db_val is not None:
        try:
            return float(db_val), "db"
        except (TypeError, ValueError):
            pass
    return 0.0, "fallback-zero"


def _step_single_date(
    station: dict,
    rain_series: pd.Series,
    cur_date: date,
    last_raw: float,
    prev_raw: float,
    client_rainfall: dict[str, float] | None = None,
    batch_state: dict | None = None,
    source: str | None = None,
) -> tuple[dict, float, float]:
    """Compute (or reuse) ONE date: rainfall -> window -> model -> persist.

    Dates that already have a stored flow row are NEVER recomputed: the chain
    advances with the stored value and stored rainfall (source 'db'), so
    backfill never rewrites history. Missing dates get the full live pipeline
    and are persisted (rainfall via INSERT OR IGNORE, flow via INSERT OR
    REPLACE with the caller's source tag).

    Returns (audit, new_last_raw, new_prev_raw). audit always carries
    date/rainfall_mm/rainfall_source/computed; computed rows also carry
    pred_raw_streamflow.
    """
    from database import (
        get_rainfall_for_date, insert_rainfall, insert_gauge_state, query_one
    )
    sid = station["station_id"]
    cur_str = cur_date.isoformat()

    existing = query_one(
        "SELECT raw_streamflow FROM gauge_state WHERE station_id = ? AND date = ?",
        [sid, cur_str],
    )
    if existing is not None:
        flow_val = float(existing["raw_streamflow"])
        db_rain = get_rainfall_for_date(sid, cur_str)
        if db_rain is None and client_rainfall and cur_str in client_rainfall:
            try:
                rain_val = float(client_rainfall[cur_str])
                insert_rainfall(sid, cur_str, rain_val)
                rain_src = "client"
            except (TypeError, ValueError):
                rain_val, rain_src = 0.0, "fallback-zero"
        else:
            try:
                rain_val = float(db_rain) if db_rain is not None else 0.0
            except (TypeError, ValueError):
                rain_val = 0.0
            rain_src = "db" if db_rain is not None else "fallback-zero"
        rain_series[pd.Timestamp(cur_date)] = rain_val
        audit = {
            "date": cur_str,
            "computed": False,
            "rainfall_mm": round(rain_val, 2),
            "rainfall_source": rain_src,
        }
        return audit, flow_val, last_raw

    rain_val, rain_src = _resolve_rainfall_for_date(
        station, cur_str, client_rainfall, batch_state
    )
    insert_rainfall(sid, cur_str, rain_val)
    predictor = get_predictor()
    df_window = build_feature_window(station, rain_series, last_raw, prev_raw, cur_date)
    x_dynamic, x_flat = preprocess_window(df_window, predictor)
    result = predictor.predict(x_dynamic, x_flat, last_raw)
    flow_val = clamp_flow(result["pred_raw_streamflow"])
    insert_gauge_state(sid, cur_str, flow_val, source)
    rain_series[pd.Timestamp(cur_date)] = rain_val
    audit = {
        "date": cur_str,
        "computed": True,
        "rainfall_mm": round(rain_val, 2),
        "rainfall_source": rain_src,
        "pred_raw_streamflow": round(flow_val, 2),
    }
    return audit, flow_val, last_raw


def ensure_anchor_to_today(
    station: dict,
    rain_series: pd.Series,
    last_date: date,
    last_raw: float,
    prev_raw: float,
    today: date,
    client_rainfall: dict[str, float] | None = None,
    source: str | None = None,
) -> tuple[float, float, list[dict]]:
    """Fill the anchor->today gap sequentially. Shared by both public functions.

    anchor (last_date) is the latest persisted gauge_state date — the CDS
    baseflow download date (currently 2026-09-22) on a fresh DB. Every date in
    last_date+1..today goes through _step_single_date (live rainfall attempt +
    window + chained predict + persist). No-op when last_date >= today.

    Returns (new_last_raw, new_prev_raw, audits) — audits in chronological
    order, one entry per gap date (computed or reused).
    """
    audits: list[dict] = []
    if last_date >= today:
        return last_raw, prev_raw, audits
    batch_state: dict = {"cache": None, "live_disabled": False,
                         "end": today.isoformat()}
    cur = last_date + timedelta(days=1)
    while cur <= today:
        audit, last_raw, prev_raw = _step_single_date(
            station, rain_series, cur, last_raw, prev_raw,
            client_rainfall, batch_state, source,
        )
        audits.append(audit)
        cur += timedelta(days=1)
    return last_raw, prev_raw, audits


# ── Single-station prediction ────────────────────────────────────────

def run_prediction_for_station(station_id: int, target_date: date, client_rainfall: dict[str, float] | None = None) -> dict:
    """
    Predict streamflow for a given station and date.
    Dynamically fills any historical gaps up to target_date and saves the results to DB.
    """
    from database import (
        get_station, get_rainfall_history, get_gauge_state,
        insert_rainfall, insert_gauge_state, get_rainfall_for_date,
        query_one
    )
    
    station = get_station(station_id)
    if not station:
        raise ValueError(f"Station {station_id} not found")
        
    target_str = target_date.isoformat()
    today = _today_ist()

    # Reload rain history
    rain_history = get_rainfall_history(station_id)
    rain_series = pd.Series(
        [r["rainfall_mm"] for r in rain_history],
        index=pd.to_datetime([r["date"] for r in rain_history])
    )

    # Anchor = latest persisted gauge_state date (CDS baseflow date on a fresh DB)
    flow_rows = get_gauge_state(station_id, limit=2)
    if flow_rows:
        last_date = date.fromisoformat(flow_rows[0]["date"])
        last_raw = flow_rows[0]["raw_streamflow"]
        prev_raw = flow_rows[1]["raw_streamflow"] if len(flow_rows) > 1 else last_raw
    else:
        last_date = target_date - timedelta(days=60)
        last_raw = 0.0
        prev_raw = 0.0

    # Phase A (guarantee): anchor -> today with per-date live dynamic
    # features. Always runs, even when target <= today ("backfill then extend").
    last_raw, prev_raw, gap_audits = ensure_anchor_to_today(
        station, rain_series, last_date, last_raw, prev_raw, today,
        client_rainfall, source=None,
    )

    # Phase B: extend to the target when it lies beyond today (or beyond the
    # anchor when the DB already reaches past today).
    covered_through = max(last_date, today)
    if covered_through < target_date:
        batch_state = {"cache": None, "live_disabled": False,
                       "end": target_date.isoformat()}
        cur = covered_through + timedelta(days=1)
        while cur <= target_date:
            audit, last_raw, prev_raw = _step_single_date(
                station, rain_series, cur, last_raw, prev_raw,
                client_rainfall, batch_state, None,
            )
            cur += timedelta(days=1)
            
    # Now query target_date prediction values from DB to construct response
    db_flow_row = query_one("SELECT raw_streamflow FROM gauge_state WHERE station_id = ? AND date = ?", [station_id, target_str])
    pred_raw_streamflow = db_flow_row["raw_streamflow"] if db_flow_row else 0.0
    
    # Get last raw BEFORE target_date for anchor_streamflow
    # before_date excludes target, so index 0 is the latest actual before target.
    flow_rows_before = get_gauge_state(station_id, limit=2, before_date=target_str)
    if len(flow_rows_before) >= 1:
        anchor_streamflow = flow_rows_before[0]["raw_streamflow"]
        prev_raw_t = flow_rows_before[0]["raw_streamflow"]  # for window reconstruction
    else:
        anchor_streamflow = 0.0
        prev_raw_t = 0.0
        
    pred_delta_raw = pred_raw_streamflow - anchor_streamflow
    db_rain = get_rainfall_for_date(station_id, target_str)
    rainfall_mm = db_rain if db_rain is not None else 0.0
    
    # Rebuild final df_window for target_date to return correct debug_features
    df_window = build_feature_window(station, rain_series, anchor_streamflow, prev_raw_t, target_date)
    debug_features = df_window.iloc[-1].fillna(0).to_dict()
    
    rain_window = []
    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        rain_mm = float(rain_series.get(pd.Timestamp(row_date), 0.0))
        rain_window.append({"date": row_date.isoformat(), "rainfall_mm": round(rain_mm, 2)})
        
    return {
        "station_id":           station_id,
        "station_name":         station["station_name"],
        "latitude":             station["latitude"],
        "longitude":            station["longitude"],
        "date":                 target_str,
        "rainfall_mm_fetched":  round(rainfall_mm, 2),
        "pred_raw_streamflow":  round(pred_raw_streamflow, 2),
        "pred_delta_raw":       round(pred_delta_raw, 2),
        "anchor_streamflow":    round(anchor_streamflow, 2),
        "unit":                 "m³/s",
        "rain_window":          rain_window,
        "debug_features":       debug_features,
        "backfilled_dates":     [a["date"] for a in gap_audits if a.get("computed")],
        "backfilled":           gap_audits,
    }


# ── Sequential Future Prediction (In-Memory Trajectory) ────────────────

def predict_future_streamflow(station_id: int, target_date: date, client_rainfall: dict[str, float] | None = None, source: str | None = None) -> dict:
    """
    Predict future streamflow recursively, dynamically filling gaps and saving predictions.
    Fetches rainfall forecasts dynamically and chains predictions.

    source: optional provenance tag written on inserted gauge_state rows
    (e.g. 'forecast'); None preserves the legacy untagged insert.
    """
    from database import (
        get_station, get_rainfall_history, get_gauge_state, query_one
    )

    station = get_station(station_id)
    if not station:
        raise ValueError(f"Station {station_id} not found")

    today = _today_ist()

    # Load rainfall history
    rain_history = get_rainfall_history(station_id)
    rain_series = pd.Series(
        [r["rainfall_mm"] for r in rain_history],
        index=pd.to_datetime([r["date"] for r in rain_history])
    )

    # Anchor = latest persisted gauge_state date (CDS baseflow date on fresh DB)
    flow_rows = get_gauge_state(station_id, limit=2)
    if flow_rows:
        last_date = date.fromisoformat(flow_rows[0]["date"])
        last_raw = flow_rows[0]["raw_streamflow"]
        prev_raw = flow_rows[1]["raw_streamflow"] if len(flow_rows) > 1 else last_raw
    else:
        last_date = today - timedelta(days=60)
        last_raw = 0.0
        prev_raw = 0.0

    # Step 1 (guarantee): anchor -> today, per-date live dynamic features.
    # Always runs, even when target <= today ("backfill then extend").
    last_raw, prev_raw, gap_audits = ensure_anchor_to_today(
        station, rain_series, last_date, last_raw, prev_raw, today,
        client_rainfall, source,
    )
    covered_through = max(last_date, today)

    # Step 2: future trajectory from covered_through+1 up to the target.
    # When target <= today this loop is empty and the target is answered
    # from the now-persisted rows below (never an empty success).
    start_date = covered_through + timedelta(days=1)
    batch_state = {"cache": None, "live_disabled": False,
                   "end": target_date.isoformat()}

    trajectory = []
    current_date = start_date

    while current_date <= target_date:
        current_str = current_date.isoformat()
        anchor_before = last_raw
        audit, last_raw, prev_raw = _step_single_date(
            station, rain_series, current_date, last_raw, prev_raw,
            client_rainfall, batch_state, source,
        )
        fetched_rain = audit["rainfall_mm"]
        pred_raw_streamflow = last_raw
        pred_delta_raw = pred_raw_streamflow - anchor_before

        trajectory.append({
            "date": current_str,
            "anchor_streamflow": round(anchor_before, 2),
            "rainfall_mm_fetched": round(fetched_rain, 2),
            "pred_delta_raw": round(pred_delta_raw, 2),
            "pred_raw_streamflow": round(pred_raw_streamflow, 2)
        })

        current_date += timedelta(days=1)

    # Rebuild final df_window for target_date to return correct debug_features.
    # Rows are now guaranteed persisted (gap + extension), so read back the
    # two latest rows strictly before the target.
    flow_rows_before = get_gauge_state(station_id, limit=3, before_date=target_date.isoformat())
    if len(flow_rows_before) > 1:
        if flow_rows_before[0]["date"] == target_date.isoformat():
            last_raw_t = flow_rows_before[1]["raw_streamflow"]
            prev_raw_t = flow_rows_before[2]["raw_streamflow"] if len(flow_rows_before) > 2 else last_raw_t
        else:
            last_raw_t = flow_rows_before[0]["raw_streamflow"]
            prev_raw_t = flow_rows_before[1]["raw_streamflow"]
    elif len(flow_rows_before) == 1:
        if flow_rows_before[0]["date"] == target_date.isoformat():
            last_raw_t = 0.0
            prev_raw_t = 0.0
        else:
            last_raw_t = flow_rows_before[0]["raw_streamflow"]
            prev_raw_t = last_raw_t
    else:
        last_raw_t = 0.0
        prev_raw_t = 0.0
    df_window = build_feature_window(station, rain_series, last_raw_t, prev_raw_t, target_date)

    debug_features = df_window.iloc[-1].fillna(0).to_dict()

    rain_window = []
    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        rain_mm = float(rain_series.get(pd.Timestamp(row_date), 0.0))
        rain_window.append({"date": row_date.isoformat(), "rainfall_mm": round(rain_mm, 2)})

    # Answer the target from the now-persisted rows (works for past targets
    # too — never an empty success).
    target_str = target_date.isoformat()
    target_row = query_one(
        "SELECT raw_streamflow FROM gauge_state WHERE station_id = ? AND date = ?",
        [station_id, target_str],
    )
    target_flow = float(target_row["raw_streamflow"]) if target_row else 0.0
    before_rows = get_gauge_state(station_id, limit=1, before_date=target_str)
    anchor_flow = float(before_rows[0]["raw_streamflow"]) if before_rows else 0.0

    return {
        "trajectory": trajectory,
        "debug_features": debug_features,
        "rain_window": rain_window,
        "target": target_str,
        "pred_raw_streamflow": round(target_flow, 2),
        "pred_delta_raw": round(target_flow - anchor_flow, 2),
        "anchor_streamflow": round(anchor_flow, 2),
        "backfilled_dates": [a["date"] for a in gap_audits if a.get("computed")],
        "backfilled": gap_audits,
    }


# ── Autonomous Background Sync Engine ─────────────────────────────────

def sync_historical_predictions():
    """
    Checks how far behind gauge_state is from date.today(), 
    and iterates forward day-by-day to accurately backfill missing days.
    """
    from database import get_all_stations, get_gauge_state, insert_rainfall
    
    target_date = date.today()
    target_str  = target_date.isoformat()
    stations    = get_all_stations()

    print(f"\n{'='*60}")
    print(f"🔄 Auto-Sync Engine checking db gap against target: {target_str}")
    print(f"   Processing {len(stations)} stations...")
    print(f"{'='*60}")

    # ── 1. Find the earliest missing date across all stations ───────────
    earliest_missing = None
    for station in stations:
        flow_rows = get_gauge_state(station["station_id"], limit=1)
        if flow_rows:
            last_date = date.fromisoformat(flow_rows[0]["date"])
            missing_start = last_date + timedelta(days=1)
            if missing_start <= target_date:
                if earliest_missing is None or missing_start < earliest_missing:
                    earliest_missing = missing_start

    # ── 2. Pre-fetch rainfall in a single multi-location batch call ───
    if earliest_missing is not None:
        start_str = earliest_missing.isoformat()
        end_str = target_date.isoformat()
        print(f"🌧️  Missing rainfall from {start_str} to {end_str}.")
        print("❌ Render auto-sync is DISABLED to avoid Open-Meteo 429 bans.")
        print("Please run `python local_bootstrap.py` on your laptop to push rainfall data.")
        return

    # ── 3. Run predictions as normal (will read rainfall from database cache) ───
    success = 0
    failed  = 0
    skipped = 0

    for idx, station in enumerate(stations):
        sid = station["station_id"]
        try:
            # Find the most recent entry
            flow_rows = get_gauge_state(sid, limit=1)
            if not flow_rows:
                skipped += 1
                continue
                
            last_date_str = flow_rows[0]["date"]
            last_date = date.fromisoformat(last_date_str)
            
            # Forward simulate strictly missing days
            current_date = last_date + timedelta(days=1)
            
            if current_date > target_date and idx == 0:
                print("   Database is fully up-to-date. No syncing required.")
                
            while current_date <= target_date:
                run_prediction_for_station(sid, current_date)
                success += 1
                current_date += timedelta(days=1)
                
        except Exception as e:
            print(f"  ❌ Auto-Sync Station {sid} failed: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"🏁 Auto-Sync complete: {success} newly generated predictions, {failed} failed")
    print(f"{'='*60}\n")
