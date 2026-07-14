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
from datetime import date, timedelta
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


# ── Single-station prediction ────────────────────────────────────────

def run_prediction_for_station(station_id: int, target_date: date) -> dict:
    """
    Run the full prediction pipeline for a single station on a given date.
    Returns the prediction result dict or raises an exception.
    """
    # Import here to avoid circular imports
    from database import (
        get_station, get_rainfall_history, get_gauge_state,
        insert_rainfall, cleanup_old_rainfall,
        insert_gauge_state, cleanup_old_gauge_state,
        get_rainfall_for_date
    )

    station = get_station(station_id)
    if not station:
        raise ValueError(f"Station {station_id} not found")

    target_str = target_date.isoformat()

    # ── 1. Check if rainfall is already in database ───────────────────
    db_rain = get_rainfall_for_date(station_id, target_str)
    if db_rain is not None:
        rainfall_mm = db_rain
    else:
        # Fetch from Open-Meteo as fallback
        rainfall_mm = fetch_rainfall_mm(
            station["latitude"], station["longitude"], target_str
        )
        insert_rainfall(station_id, target_str, rainfall_mm)

    cutoff_rain = (target_date - timedelta(days=60)).isoformat()
    cleanup_old_rainfall(station_id, cutoff_rain)

    # ── 3. Load rainfall history (last 60 days) ──────────────────────
    rain_history = get_rainfall_history(station_id)
    rain_series = pd.Series(
        [r["rainfall_mm"] for r in rain_history],
        index=pd.to_datetime([r["date"] for r in rain_history])
    )

    # ── 4. Load gauge_state (last 2 flow values BEFORE target_date) ──
    # We must restrict to dates < target_date so that re-running a prediction
    # for the same date always anchors to yesterday's streamflow, not the
    # value written by a previous run for today.
    flow_rows = get_gauge_state(station_id, limit=2, before_date=target_str)
    if flow_rows:
        last_raw = flow_rows[0]["raw_streamflow"]
        prev_raw = flow_rows[1]["raw_streamflow"] if len(flow_rows) > 1 else last_raw
    else:
        last_raw = 0.0
        prev_raw = 0.0

    # ── 5. Build 15-row feature window ────────────────────────────────
    df_window = build_feature_window(station, rain_series, last_raw, prev_raw, target_date)

    # ── 6. Preprocess + Predict ────────────────────────────────────────
    predictor = get_predictor()
    x_dynamic, x_flat = preprocess_window(df_window, predictor)
    result = predictor.predict(x_dynamic, x_flat, last_raw)

    # ── 7. Write to gauge_state, clean old rows ──────────────────────
    insert_gauge_state(station_id, target_str, result["pred_raw_streamflow"])
    cutoff_gauge = (target_date - timedelta(days=20)).isoformat()
    cleanup_old_gauge_state(station_id, cutoff_gauge)

    # Convert the last row of df_window to a dictionary representing feature values used
    debug_features = df_window.iloc[-1].fillna(0).to_dict()

    # Build the 15-day rainfall window for display
    rain_window = []
    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        row_date_str = row_date.isoformat()
        rain_mm = float(rain_series.get(pd.Timestamp(row_date), 0.0))
        rain_window.append({"date": row_date_str, "rainfall_mm": round(rain_mm, 2)})

    return {
        "station_id":           station_id,
        "station_name":         station["station_name"],
        "latitude":             station["latitude"],
        "longitude":            station["longitude"],
        "date":                 target_str,
        "rainfall_mm_fetched":  round(rainfall_mm, 2),
        "pred_raw_streamflow":  round(result["pred_raw_streamflow"], 2),
        "pred_delta_raw":       round(result["pred_delta_raw"], 2),
        "anchor_streamflow":    round(last_raw, 2),
        "unit":                 "m³/s",
        "rain_window":          rain_window,
        "debug_features":       debug_features,
    }


# ── Sequential Future Prediction (In-Memory Trajectory) ────────────────

def predict_future_streamflow(station_id: int, target_date: date) -> dict:
    """
    Predict future streamflow recursively without modifying the database.
    Fetches rainfall forecasts dynamically and chains predictions internally.
    """
    from database import get_station, get_rainfall_history, get_gauge_state
    
    station = get_station(station_id)
    if not station:
        raise ValueError(f"Station {station_id} not found")
        
    start_date = date.today() + timedelta(days=1)
    if target_date < start_date:
        raise ValueError("predict_future_streamflow called for non-future date")
        
    # Load historical rainfall to seed the window memory
    rain_history = get_rainfall_history(station_id)
    rain_series = pd.Series(
        [r["rainfall_mm"] for r in rain_history],
        index=pd.to_datetime([r["date"] for r in rain_history])
    )
    
    # Load actual original gauge states
    flow_rows = get_gauge_state(station_id, limit=2)
    if flow_rows:
        last_raw = flow_rows[0]["raw_streamflow"]
        prev_raw = flow_rows[1]["raw_streamflow"] if len(flow_rows) > 1 else last_raw
    else:
        last_raw = 0.0
        prev_raw = 0.0

    # Fetch forecasted rainfall explicitly (from tomorrow up to target)
    forecast_rain = fetch_rainfall_batch(
        station["latitude"], station["longitude"], 
        start_date.isoformat(), target_date.isoformat()
    )
    
    trajectory = []
    current_date = start_date
    predictor = get_predictor()
    
    while current_date <= target_date:
        current_str = current_date.isoformat()
        
        # Add forecasted rain to the rolling series
        fetched_rain = forecast_rain.get(current_str, 0.0)
        rain_series[pd.Timestamp(current_date)] = fetched_rain
        
        # Build window & Predict in memory
        df_window = build_feature_window(station, rain_series, last_raw, prev_raw, current_date)
        x_dynamic, x_flat = preprocess_window(df_window, predictor)
        result = predictor.predict(x_dynamic, x_flat, last_raw)
        
        trajectory.append({
            "date": current_str,
            "anchor_streamflow": round(last_raw, 2),
            "rainfall_mm_fetched": round(fetched_rain, 2),
            "pred_delta_raw": round(result["pred_delta_raw"], 2),
            "pred_raw_streamflow": round(result["pred_raw_streamflow"], 2)
        })
        
        # Update iteration buffers for the next day
        prev_raw = last_raw
        last_raw = result["pred_raw_streamflow"]
        
        current_date += timedelta(days=1)
        
    # Build debug features and 15-day rain window for the final target_date step
    debug_features = df_window.iloc[-1].fillna(0).to_dict()

    rain_window = []
    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        rain_mm = float(rain_series.get(pd.Timestamp(row_date), 0.0))
        rain_window.append({"date": row_date.isoformat(), "rainfall_mm": round(rain_mm, 2)})

    return {
        "trajectory": trajectory,
        "debug_features": debug_features,
        "rain_window": rain_window
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
        print(f"🌧️  Pre-fetching missing rainfall from {start_str} to {end_str} for all stations in one API request...")
        
        stations_coords = [
            {"station_id": s["station_id"], "latitude": s["latitude"], "longitude": s["longitude"]}
            for s in stations
        ]
        
        multi_data = fetch_rainfall_batch_multi(stations_coords, start_str, end_str)
        if multi_data:
            inserted_count = 0
            for item in multi_data:
                sid = item["station_id"]
                daily = item.get("daily", {})
                dates = daily.get("time", [])
                precips = daily.get("precipitation_sum", [])
                
                for d_str, p_val in zip(dates, precips):
                    val = float(p_val) if p_val is not None else 0.0
                    insert_rainfall(sid, d_str, val)
                    inserted_count += 1
            print(f"   Successfully pre-fetched & cached {inserted_count} rainfall records.")
        else:
            print("   ⚠️  Failed to pre-fetch rainfall in batch. Falls back to individual API calls during prediction.")

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
