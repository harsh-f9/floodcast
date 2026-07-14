"""
July 2024 Streamflow Batch Predictor
=====================================
Predicts daily streamflow and flood severity for 27 gauges across July 2024.

Strategy:
  - Anchors on July 1 observed streamflow from the input CSV.
  - Fetches historical rainfall May 1-July 31 2024 from Open-Meteo Archive API.
  - Chains predictions July 2 -> July 31 fully in memory (no DB writes).
  - Outputs two CSVs to results/:
      july2024_predictions.csv  -- one row per (gauge x day)
      july2024_summary.csv      -- one row per gauge (peak flow, peak date, peak severity)

Usage:
    cd d:\\crowebsite\\crowebsite
    C:\\Users\\DELL\\anaconda3\\python.exe july2024_batch\\run_july2024.py
"""

import os
import sys
import io
import time

# Force UTF-8 output on Windows to handle emoji in existing predictor.py prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
import numpy as np
import pandas as pd
from datetime import date, timedelta

# ---- Path setup: point to existing backend code -----------------------------
THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.dirname(THIS_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FLOOD_DIR   = os.path.join(BACKEND_DIR, "Flood_prediction")
DEPLOY_DIR  = os.path.join(FLOOD_DIR, "deploy")
RESULTS_DIR = os.path.join(THIS_DIR, "results")

for p in [FLOOD_DIR, DEPLOY_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Now we can import the existing model/feature logic
from predictor import StreamflowPredictor   # from deploy/

# ---- Constants ---------------------------------------------------------------
INPUT_CSV    = r"C:\Users\DELL\Downloads\Browser Downloads\Edge\streamflow_results_july1.csv"
GAUGES_CSV   = os.path.join(DEPLOY_DIR, "gauges_info.csv")
ARCHIVE_URL  = "https://archive-api.open-meteo.com/v1/archive"

JULY_START   = date(2024, 7, 1)   # Anchor date (observed, not predicted)
JULY_2       = date(2024, 7, 2)   # First predicted date
JULY_END     = date(2024, 7, 31)  # Last predicted date

# Need 60 days of antecedent rainfall before July 1 for the feature window
LOOKBACK_START = JULY_START - timedelta(days=60)   # 2024-05-02
FETCH_START    = LOOKBACK_START.isoformat()
FETCH_END      = JULY_END.isoformat()

# ---- Severity thresholds (matches frontend getRiskStatus) --------------------
def get_severity(flow, rp_2, rp_5, rp_15, rp_20):
    if flow < rp_2:  return "NORMAL"
    if flow < rp_5:  return "WATCH"
    if flow < rp_15: return "WARNING"
    if flow < rp_20: return "DANGER"
    return "EXTREME"


# ---- Feature engineering helpers (mirrors prediction_service.py) -------------

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


def compute_return_period(streamflow, rp_2, rp_5, rp_15):
    """Matches prediction_service.compute_return_period exactly."""
    if streamflow < rp_2:
        return streamflow / (rp_2 + 0.1)
    elif streamflow < rp_5:
        return 2 + (streamflow - rp_2) / (rp_2 * 0.33)
    else:
        return 5 + (streamflow - rp_5) / (rp_5 * 0.25)


def build_feature_window(station, rain_series, last_raw, prev_raw, target_date):
    """
    Mirrors prediction_service.build_feature_window exactly.
    Builds a 15-row DataFrame covering [target_date-14d .. target_date].
    """
    window_rows = []

    for i in range(15):
        row_date = target_date - timedelta(days=(14 - i))
        row_rain = rain_series.get(pd.Timestamp(row_date), 0.0)

        rain_slice = rain_series[rain_series.index <= pd.Timestamp(row_date)]
        r3   = float(rain_slice.tail(3).sum())
        r7   = float(rain_slice.tail(7).sum())
        r15  = float(rain_slice.tail(15).sum())
        r30  = float(rain_slice.tail(30).sum())
        r60  = float(rain_slice.tail(60).sum())
        ewm  = float(rain_slice.ewm(span=30).mean().iloc[-1]) if len(rain_slice) else 0.0
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

        prev_day_rain = rain_series.get(pd.Timestamp(row_date - timedelta(1)), 0.0)

        window_rows.append({
            "rainfall_mm":                        row_rain,
            "rainfall_mm_log":                    np.log1p(row_rain),
            "rainfall_mm_log_delta":              np.log1p(row_rain) - np.log1p(prev_day_rain),
            "antecedent_rain_3d_sum":             r3,
            "antecedent_rain_7d_sum":             r7,
            "antecedent_rain_15d_sum":            r15,
            "antecedent_rain_30d_sum":            r30,
            "antecedent_rain_60d":                r60,
            "antecedent_rain_ewm":                ewm,
            "antecedent_rain_30d_sum_log":        r30_log,
            "monsoon_cumulative_rain":            monsoon_rain,
            "antecedent_rain_3d_mean":            r3 / 3.0,
            "antecedent_rain_7d_mean":            r7 / 7.0,
            "antecedent_rain_15d_mean":           r15 / 15.0,
            "antecedent_rain_30d_mean":           r30 / 30.0,
            "monsoon_intensity":                  1 if m in [6, 7, 8, 9, 10] else 0,
            "is_post_monsoon_saturated":          1 if m in [10, 11] else 0,
            "month_sin":                          np.sin(2 * np.pi * (m - 1) / 12),
            "month_cos":                          np.cos(2 * np.pi * (m - 1) / 12),
            "doy_sin":                            np.sin(2 * np.pi * doy / 365),
            "doy_cos":                            np.cos(2 * np.pi * doy / 365),
            "soil_saturation_score":              ss_score,
            "antecedent_saturation_interaction":  ss_score * r7,
            "flow_rate_of_change":                (last_raw - prev_raw) / (prev_raw + 1e-6),
            "estimated_return_period":            erp,
            "flow_rp15_ratio":                    last_raw / (station["rp_15"] + 1e-6),
            "upstream_rain_mean":                 row_rain,
            "weighted_upstream_rain":             row_rain,
            "upstream_rain_lagged_dist_sink":     row_rain * (station["DIST_SINK"] / (station["flow_velocity_km_per_day"] + 1e-6)),
            "rain_urban_interaction":             row_rain * station["urb_pc"],
            "rain_slope_interaction":             row_rain * station["slp_dg"],
            "rain_basin_size_interaction":        row_rain * station["UP_AREA"],
            "rain_monthly_swc_interaction":       row_rain * r30,
            "uparea_upstream_rain_interaction":   station["UP_AREA"] * row_rain,
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
            # Upstream gauges unavailable -- zeroed (same as original)
            "upstream_weighted_streamflow_log":        0.0,
            "upstream_weighted_streamflow_log_delta":  0.0,
            "upstream_lag1_streamflow_log_delta":      0.0,
            "upstream_lag2_streamflow_log_delta":      0.0,
        })

    return pd.DataFrame(window_rows)


def preprocess_window(df_window, predictor):
    """
    Mirrors prediction_service.preprocess_window exactly.
    Returns x_dynamic (15, 32) and x_flat (42,).
    """
    df = df_window.copy()

    # Step 1: Yeo-Johnson
    df[YJ_RAW_COLS] = predictor.yj_transformer.transform(df[YJ_RAW_COLS])
    rename_map = {col: f"{col}_yj" for col in YJ_RAW_COLS}
    df = df.rename(columns=rename_map)

    # Step 2: MinMax
    df[MM_COLS] = predictor.mm_scaler.transform(df[MM_COLS])

    # Step 3: Standard scaler
    df[STANDARD_FEATURE_COLS] = predictor.feature_scaler.transform(df[STANDARD_FEATURE_COLS])

    # Step 4: Extract in exact column order from model config
    x_dynamic = df[predictor.dynamic_cols].values.astype(np.float32)       # (15, 32)
    x_flat    = df[predictor.flat_cols].iloc[-1].values.astype(np.float32)  # (42,)

    return x_dynamic, x_flat


# ---- Rainfall fetching from Archive API -------------------------------------

def fetch_rainfall_archive(lat, lon, start_date, end_date):
    """
    Fetch rainfall from Open-Meteo Archive API for a date range.
    Returns dict: {date_str: rainfall_mm}
    """
    try:
        r = requests.get(ARCHIVE_URL, params={
            "latitude":   lat,
            "longitude":  lon,
            "daily":      "precipitation_sum",
            "start_date": start_date,
            "end_date":   end_date,
            "timezone":   "Asia/Kolkata",
        }, timeout=30)
        r.raise_for_status()
        data = r.json()["daily"]
        result = {}
        for d, p in zip(data["time"], data["precipitation_sum"]):
            result[d] = float(p) if p is not None else 0.0
        return result
    except Exception as e:
        print(f"    [!] Archive fetch failed ({lat},{lon}): {e}")
        return {}


# ---- Main runner -------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("=" * 65)
    print("  July 2024 Streamflow Batch Predictor")
    print("=" * 65)

    # 1. Load input CSV (July 1 observed streamflow)
    print(f"\n[*] Loading input CSV: {INPUT_CSV}")
    input_df = pd.read_csv(INPUT_CSV)
    print(f"    Found {len(input_df)} gauges.")

    # 2. Load gauges_info.csv (static features)
    print(f"[*] Loading gauge info: {GAUGES_CSV}")
    gauges_info = pd.read_csv(GAUGES_CSV)
    # Build lookup: gauge_id -> static row
    gauge_lookup = {}
    for _, row in gauges_info.iterrows():
        gid = str(row["gauge_id"]).strip()
        gauge_lookup[gid] = row.to_dict()
    print(f"    Loaded {len(gauge_lookup)} gauge static records.")

    # 3. Load LSTM+XGBoost predictor
    print(f"\n[*] Loading StreamflowPredictor from: {DEPLOY_DIR}")
    predictor = StreamflowPredictor(DEPLOY_DIR + "/")
    print()

    # 4. Predict for each gauge
    all_rows     = []   # Detailed predictions
    summary_rows = []   # Per-gauge summary

    for gauge_idx, input_row in input_df.iterrows():
        gauge_id   = str(input_row["gauge_id"]).strip()
        lat        = float(input_row["latitude"])
        lon        = float(input_row["longitude"])
        july1_flow = float(input_row["streamflow_m3s"])

        print(f"\n[{gauge_idx + 1:02d}/{len(input_df)}] Gauge: {gauge_id}")
        print(f"         Lat={lat:.4f}, Lon={lon:.4f}, July1 flow={july1_flow:.3f} m3/s")

        # 4a. Resolve static features
        if gauge_id not in gauge_lookup:
            print(f"    [!] Gauge {gauge_id} not found in gauges_info.csv -- skipping.")
            continue

        static = gauge_lookup[gauge_id]
        station = {
            "UP_AREA":                  float(static.get("UP_AREA", 0.0)),
            "DIST_SINK":                float(static.get("DIST_SINK", 0.0)),
            "slp_dg":                   float(static.get("slp_dg", 0.0)),
            "slp_dg_uav":               float(static.get("slp_dg_uav", 0.0)),
            "for_pc":                   float(static.get("for_pc", 0.0)),
            "urb_pc":                   float(static.get("urb_pc", 0.0)),
            "attenuation_factor":       float(static.get("attenuation_factor", 0.0)),
            "flow_velocity_km_per_day": float(static.get("flow_velocity_km_per_day", 0.0)),
            "upstream_lag1_days":       float(static.get("upstream_lag1_days", 1.0)),
            "upstream_lag2_days":       float(static.get("upstream_lag2_days", 1.0)),
            "rp_2":                     float(static.get("rp_2", 0.0)),
            "rp_5":                     float(static.get("rp_5", 0.0)),
            "rp_15":                    float(static.get("rp_15", 0.0)),
            "rp_20":                    float(static.get("rp_20", 0.0)),
            "max_30d_rain":             1.0,   # Placeholder; computed below
        }

        # 4b. Fetch historical rainfall from Archive API
        print(f"    [rain] Fetching rainfall {FETCH_START} -> {FETCH_END}...")
        rain_data = fetch_rainfall_archive(lat, lon, FETCH_START, FETCH_END)
        time.sleep(0.15)   # Polite rate-limiting

        if not rain_data:
            print(f"    [!] No rainfall data -- skipping gauge.")
            continue

        # Build rain_series with DatetimeIndex
        rain_series = pd.Series(
            {pd.Timestamp(d): v for d, v in sorted(rain_data.items())}
        )

        # Compute max_30d_rain from the antecedent period (ending June 30)
        pre_july = rain_series[rain_series.index < pd.Timestamp(JULY_START)]
        if len(pre_july) >= 30:
            max_30d = float(pre_july.rolling(30).sum().max())
        else:
            max_30d = float(pre_july.sum())
        station["max_30d_rain"] = max(max_30d, 1.0)

        print(f"    [=]  max_30d_rain={station['max_30d_rain']:.1f} mm  | "
              f"rain days fetched={len(rain_data)}")

        # 4c. Chain predictions July 2 -> July 31
        last_raw = july1_flow   # Anchor: July 1 observed
        prev_raw = july1_flow   # For July 2, we only have one prior point

        gauge_rows    = []
        peak_flow     = july1_flow
        peak_date_str = JULY_START.isoformat()
        peak_sev      = get_severity(
            july1_flow,
            station["rp_2"], station["rp_5"],
            station["rp_15"], station["rp_20"]
        )

        current_date = JULY_2
        while current_date <= JULY_END:
            date_str = current_date.isoformat()

            # Build 15-row feature window
            df_window = build_feature_window(
                station, rain_series, last_raw, prev_raw, current_date
            )

            # Preprocess + predict
            x_dynamic, x_flat = preprocess_window(df_window, predictor)
            result = predictor.predict(x_dynamic, x_flat, last_raw)

            pred_flow = result["pred_raw_streamflow"]
            delta     = result["pred_delta_raw"]
            rain_mm   = rain_data.get(date_str, 0.0)
            severity  = get_severity(
                pred_flow,
                station["rp_2"], station["rp_5"],
                station["rp_15"], station["rp_20"]
            )

            gauge_rows.append({
                "gauge_id":          gauge_id,
                "latitude":          lat,
                "longitude":         lon,
                "date":              date_str,
                "anchor_streamflow": round(last_raw, 4),
                "rainfall_mm":       round(rain_mm, 4),
                "pred_streamflow":   round(pred_flow, 4),
                "delta_m3s":         round(delta, 4),
                "severity":          severity,
            })

            # Track peak
            if pred_flow > peak_flow:
                peak_flow     = pred_flow
                peak_date_str = date_str
                peak_sev      = severity

            # Advance chain
            prev_raw = last_raw
            last_raw = pred_flow
            current_date += timedelta(days=1)

        all_rows.extend(gauge_rows)
        summary_rows.append({
            "gauge_id":       gauge_id,
            "latitude":       lat,
            "longitude":      lon,
            "july1_observed": round(july1_flow, 4),
            "peak_flow":      round(peak_flow, 4),
            "peak_date":      peak_date_str,
            "peak_severity":  peak_sev,
            "rp_2":           station["rp_2"],
            "rp_5":           station["rp_5"],
            "rp_15":          station["rp_15"],
            "rp_20":          station["rp_20"],
        })

        print(f"    [OK] Done -- Peak: {peak_flow:.1f} m3/s on {peak_date_str} [{peak_sev}]")

    # 5. Write output CSVs
    detail_path  = os.path.join(RESULTS_DIR, "july2024_predictions.csv")
    summary_path = os.path.join(RESULTS_DIR, "july2024_summary.csv")

    detail_df  = pd.DataFrame(all_rows)
    summary_df = pd.DataFrame(summary_rows)

    detail_df.to_csv(detail_path, index=False)
    summary_df.to_csv(summary_path, index=False)

    print(f"\n{'=' * 65}")
    print(f"[OK] Predictions complete!")
    print(f"     Gauges processed : {len(summary_rows)}/{len(input_df)}")
    print(f"     Total predictions: {len(all_rows)}")
    print(f"\n[>] Detailed output  -> {detail_path}")
    print(f"[>] Summary output   -> {summary_path}")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    main()
