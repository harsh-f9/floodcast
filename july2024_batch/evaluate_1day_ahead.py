import os
import sys
import io
import pandas as pd
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(THIS_DIR)
FLOOD_DIR = os.path.join(ROOT_DIR, "backend", "Flood_prediction")
DEPLOY_DIR = os.path.join(FLOOD_DIR, "deploy")
for p in [FLOOD_DIR, DEPLOY_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from predictor import StreamflowPredictor

sys.path.insert(0, THIS_DIR)
from run_july2024 import (
    build_feature_window, preprocess_window, fetch_rainfall_archive,
    FETCH_START, FETCH_END, JULY_START
)

def main():
    GAUGE_ID = "hybas_4120834310"
    
    # User-provided ground truth
    ground_truth = {
        date(2024, 7, 1): 20.390625,  # Approximating July 1 to allow rate_of_change calculation for July 3
        date(2024, 7, 2): 20.390625,
        date(2024, 7, 3): 807.234375,
        date(2024, 7, 4): 2234.953125,
        date(2024, 7, 5): 1760.093750,
        date(2024, 7, 6): 783.906250,
        date(2024, 7, 7): 1419.609375,
        date(2024, 7, 8): 2297.531250
    }
    
    gauges_csv = os.path.join(DEPLOY_DIR, "gauges_info.csv")
    gauges_info = pd.read_csv(gauges_csv)
    static = gauges_info[gauges_info["gauge_id"] == GAUGE_ID].iloc[0].to_dict()
    
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
    }
    
    lat = float(static["latitude"])
    lon = float(static["longitude"])
    
    print(f"Fetching rainfall for {GAUGE_ID} ({lat}, {lon})")
    rain_data = fetch_rainfall_archive(lat, lon, FETCH_START, FETCH_END)
    rain_series = pd.Series({pd.Timestamp(d): v for d, v in rain_data.items()})
    
    pre_july = rain_series[rain_series.index < pd.Timestamp(JULY_START)]
    if len(pre_july) >= 30:
        max_30d = float(pre_july.rolling(30).sum().max())
    else:
        max_30d = float(pre_july.sum())
    station["max_30d_rain"] = max(max_30d, 1.0)
    
    print("Loading StreamflowPredictor...")
    predictor = StreamflowPredictor(DEPLOY_DIR + "/")
    
    print("\n--- 1-Day Ahead Predictions using True Anchor ---\n")
    print(f"{'Date':<12} {'True Prev Day':<15} {'Rain (mm)':<10} {'Predicted':<15} {'Actual Flow':<15} {'Error':<10}")
    print("-" * 80)
    
    for i in range(3, 9):
        target_date = date(2024, 7, i)
        
        last_raw = ground_truth[target_date - timedelta(days=1)]
        prev_raw = ground_truth[target_date - timedelta(days=2)]
        actual = ground_truth[target_date]
        
        df_window = build_feature_window(station, rain_series, last_raw, prev_raw, target_date)
        x_dynamic, x_flat = preprocess_window(df_window, predictor)
        result = predictor.predict(x_dynamic, x_flat, last_raw)
        
        pred_flow = result["pred_raw_streamflow"]
        rain_mm = rain_data.get(target_date.isoformat(), 0.0)
        
        error = pred_flow - actual
        
        print(f"{target_date.isoformat():<12} {last_raw:<15.2f} {rain_mm:<10.1f} {pred_flow:<15.2f} {actual:<15.2f} {error:<10.2f}")

if __name__ == "__main__":
    main()
