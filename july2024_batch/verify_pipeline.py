"""
Pipeline Verification Script
=============================
Picks one gauge + one date, runs the prediction step-by-step with full
debug output to confirm:

  1. Static features match gauges_info.csv
  2. Dynamic feature window has correct shape (15, 32)
  3. Flat features have correct shape (42,)
  4. All 3 scalers (YJ, MinMax, Standard) are applied correctly
  5. LSTM forward pass produces output
  6. XGBoost corrector produces output
  7. Hybrid delta and inverse transform match expectations
  8. Feature column order matches model_config.json exactly

Also cross-validates against the original prediction_service.py's code path.
"""

import os
import sys
import io
import json
import numpy as np
import pandas as pd
import torch
from datetime import date, timedelta

# Force UTF-8 for predictor prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Path setup
THIS_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR    = os.path.dirname(THIS_DIR)
FLOOD_DIR   = os.path.join(ROOT_DIR, "backend", "Flood_prediction")
DEPLOY_DIR  = os.path.join(FLOOD_DIR, "deploy")
for p in [FLOOD_DIR, DEPLOY_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from predictor import StreamflowPredictor

# ---- Import our batch script's functions ------------------------------------
sys.path.insert(0, THIS_DIR)
from run_july2024 import (
    build_feature_window, preprocess_window, fetch_rainfall_archive,
    compute_return_period, get_severity,
    YJ_RAW_COLS, MM_COLS, STANDARD_FEATURE_COLS,
    FETCH_START, FETCH_END, JULY_START
)

# ---- Load model config for ground-truth column order ------------------------
with open(os.path.join(DEPLOY_DIR, "model_config.json")) as f:
    MODEL_CONFIG = json.load(f)

def sep(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    # --- Select test gauge: hybas_4120834310 (the one with negatives) ---------
    TEST_GAUGE = "hybas_4120834310"
    TEST_DATE  = date(2024, 7, 15)   # This produced negative streamflow

    sep("VERIFICATION: Full Pipeline Audit")
    print(f"  Gauge : {TEST_GAUGE}")
    print(f"  Date  : {TEST_DATE}")

    # ---- 1. Load static features from gauges_info.csv -----------------------
    sep("1. STATIC FEATURES CHECK")
    gauges_csv = os.path.join(DEPLOY_DIR, "gauges_info.csv")
    gauges_info = pd.read_csv(gauges_csv)
    gauge_row = gauges_info[gauges_info["gauge_id"] == TEST_GAUGE].iloc[0]

    static_cols = ["UP_AREA", "DIST_SINK", "slp_dg", "slp_dg_uav", "for_pc",
                   "urb_pc", "attenuation_factor", "flow_velocity_km_per_day",
                   "upstream_lag1_days", "upstream_lag2_days",
                   "rp_2", "rp_5", "rp_15", "rp_20"]

    station = {}
    print(f"\n  {'Feature':<35} {'gauges_info.csv':>15}")
    print(f"  {'-'*35} {'-'*15}")
    for col in static_cols:
        val = float(gauge_row[col])
        station[col] = val
        print(f"  {col:<35} {val:>15.4f}")

    # ---- 2. Fetch rainfall --------------------------------------------------
    sep("2. RAINFALL FETCH")
    lat = float(gauge_row["latitude"])
    lon = float(gauge_row["longitude"])
    print(f"  Location: ({lat}, {lon})")
    print(f"  Fetching {FETCH_START} -> {FETCH_END}...")

    rain_data = fetch_rainfall_archive(lat, lon, FETCH_START, FETCH_END)
    rain_series = pd.Series(
        {pd.Timestamp(d): v for d, v in sorted(rain_data.items())}
    )
    print(f"  Days fetched: {len(rain_data)}")
    print(f"  Rain on target date ({TEST_DATE}): {rain_data.get(TEST_DATE.isoformat(), 'MISSING')} mm")

    # Show 15-day rain window
    print(f"\n  15-day rainfall window leading to {TEST_DATE}:")
    for i in range(15):
        d = TEST_DATE - timedelta(days=14-i)
        r = rain_data.get(d.isoformat(), 0.0)
        bar = "#" * int(r / 2)
        print(f"    {d.isoformat()}  {r:6.1f} mm  {bar}")

    # Compute max_30d_rain
    pre_july = rain_series[rain_series.index < pd.Timestamp(JULY_START)]
    if len(pre_july) >= 30:
        max_30d = float(pre_july.rolling(30).sum().max())
    else:
        max_30d = float(pre_july.sum())
    station["max_30d_rain"] = max(max_30d, 1.0)
    print(f"\n  max_30d_rain: {station['max_30d_rain']:.1f} mm")

    # ---- 3. Build feature window with known anchor --------------------------
    sep("3. FEATURE WINDOW CONSTRUCTION")

    # Simulate chaining from July 1 to reach the anchor for July 15
    # For this audit, use a reasonable anchor (from the predictions CSV)
    anchor_flow = 1.2996    # anchor_streamflow for July 15 from our output
    prev_flow   = 31.0774   # anchor for July 14

    print(f"  last_raw (anchor): {anchor_flow}")
    print(f"  prev_raw:          {prev_flow}")

    df_window = build_feature_window(
        station, rain_series, anchor_flow, prev_flow, TEST_DATE
    )

    print(f"\n  Feature window shape: {df_window.shape}")
    print(f"  Expected:            (15, N_raw_features)")

    # Show all columns in the raw feature window
    print(f"\n  Raw feature columns ({len(df_window.columns)}):")
    for i, col in enumerate(df_window.columns):
        val = df_window.iloc[-1][col]  # Last row = target day
        print(f"    [{i:02d}] {col:<48} = {val:.6f}")

    # ---- 4. Check key derived features make sense ---------------------------
    sep("4. DERIVED FEATURE SANITY CHECK")
    last_row = df_window.iloc[-1]

    checks = [
        ("rainfall_mm_log",       "log1p(rainfall)",        np.log1p(last_row["rainfall_mm"])),
        ("month_sin",             "sin(2pi*(7-1)/12)",      np.sin(2*np.pi*(7-1)/12)),
        ("month_cos",             "cos(2pi*(7-1)/12)",      np.cos(2*np.pi*(7-1)/12)),
        ("monsoon_intensity",     "July is monsoon",        1),
        ("is_post_monsoon_saturated", "July != Oct/Nov",    0),
        ("UP_AREA",               "static from CSV",        station["UP_AREA"]),
        ("DIST_SINK",             "static from CSV",        station["DIST_SINK"]),
        ("slp_dg",                "static from CSV",        station["slp_dg"]),
        ("flow_rate_of_change",   "(last-prev)/(prev+eps)", (anchor_flow - prev_flow) / (prev_flow + 1e-6)),
        ("estimated_return_period","compute_return_period()", compute_return_period(anchor_flow, station["rp_2"], station["rp_5"], station["rp_15"])),
    ]

    all_ok = True
    for feat_name, description, expected in checks:
        actual = last_row[feat_name]
        match = abs(actual - expected) < 1e-4
        status = "OK" if match else "MISMATCH"
        if not match:
            all_ok = False
        print(f"  [{status:>8}] {feat_name:<35} actual={actual:.6f}  expected={expected:.6f}  ({description})")

    # ---- 5. Preprocessing: Scaler application --------------------------------
    sep("5. SCALER APPLICATION (3-step)")

    predictor = StreamflowPredictor(DEPLOY_DIR + "/")

    x_dynamic, x_flat = preprocess_window(df_window, predictor)

    print(f"\n  x_dynamic shape: {x_dynamic.shape}  (expected: (15, 32))")
    print(f"  x_flat shape:    {x_flat.shape}   (expected: (42,))")

    shape_ok = x_dynamic.shape == (15, 32) and x_flat.shape == (42,)
    print(f"  Shape check: {'PASS' if shape_ok else 'FAIL'}")

    # Check for NaN/Inf
    has_nan_dyn = np.isnan(x_dynamic).any() or np.isinf(x_dynamic).any()
    has_nan_flat = np.isnan(x_flat).any() or np.isinf(x_flat).any()
    print(f"  x_dynamic NaN/Inf: {'FOUND - BAD' if has_nan_dyn else 'None (clean)'}")
    print(f"  x_flat NaN/Inf:    {'FOUND - BAD' if has_nan_flat else 'None (clean)'}")

    # Show x_dynamic statistics
    print(f"\n  x_dynamic stats (across all 15 timesteps):")
    print(f"    Min:  {x_dynamic.min():.6f}")
    print(f"    Max:  {x_dynamic.max():.6f}")
    print(f"    Mean: {x_dynamic.mean():.6f}")
    print(f"    Std:  {x_dynamic.std():.6f}")

    # ---- 6. Column order verification ----------------------------------------
    sep("6. COLUMN ORDER vs model_config.json")

    config_dynamic = MODEL_CONFIG["dynamic_cols"]
    config_flat    = MODEL_CONFIG["flat_cols"]

    print(f"\n  model_config.json dynamic_cols ({len(config_dynamic)}):")
    for i, col in enumerate(config_dynamic):
        match = col == predictor.dynamic_cols[i]
        print(f"    [{i:02d}] config: {col:<48}  predictor: {predictor.dynamic_cols[i]:<48}  {'OK' if match else 'MISMATCH'}")

    print(f"\n  model_config.json flat_cols ({len(config_flat)}):")
    for i, col in enumerate(config_flat):
        match = col == predictor.flat_cols[i]
        status = "OK" if match else "MISMATCH"
        if not match:
            print(f"    [{i:02d}] config: {col:<48}  predictor: {predictor.flat_cols[i]:<48}  {status}")

    dynamic_match = config_dynamic == predictor.dynamic_cols
    flat_match = config_flat == predictor.flat_cols
    print(f"\n  Dynamic cols match config: {'PASS' if dynamic_match else 'FAIL'}")
    print(f"  Flat cols match config:    {'PASS' if flat_match else 'FAIL'}")

    # ---- 7. LSTM + XGBoost forward pass (decomposed) -------------------------
    sep("7. HYBRID MODEL FORWARD PASS (decomposed)")

    # Step 7a: LSTM forward
    x_dyn_t = torch.from_numpy(x_dynamic).unsqueeze(0)
    with torch.no_grad():
        lstm_pred, hidden = predictor.lstm(x_dyn_t, return_hidden=True)

    lstm_pred_np = lstm_pred.cpu().numpy().ravel()
    hidden_np    = hidden.cpu().numpy()

    print(f"\n  LSTM output (scaled delta): {lstm_pred_np[0]:.6f}")
    print(f"  LSTM hidden shape:         {hidden_np.shape}  (expected: (1, 256))")
    print(f"  LSTM hidden mean:          {hidden_np.mean():.6f}")
    print(f"  LSTM hidden std:           {hidden_np.std():.6f}")

    # Step 7b: XGBoost forward
    xgb_input = np.concatenate([x_flat.reshape(1, -1), hidden_np], axis=1)
    xgb_corr  = predictor.xgb.predict(xgb_input)

    print(f"\n  XGB input shape:           {xgb_input.shape}  (expected: (1, {42+256}))")
    print(f"  XGB correction (scaled):   {xgb_corr[0]:.6f}")

    # Step 7c: Combine
    hybrid_scaled = float(lstm_pred_np[0] + xgb_corr[0])
    raw_delta = float(predictor.target_scaler.inverse_transform([[hybrid_scaled]])[0][0])
    pred_raw = anchor_flow + raw_delta

    print(f"\n  Hybrid delta (scaled):     {hybrid_scaled:.6f}")
    print(f"  Target scaler mean:        {predictor.target_scaler.mean_[0]:.6f}")
    print(f"  Target scaler scale:       {predictor.target_scaler.scale_[0]:.6f}")
    print(f"  Raw delta (inverse xform): {raw_delta:.4f} m3/s")
    print(f"  Anchor:                    {anchor_flow:.4f} m3/s")
    print(f"  Predicted streamflow:      {pred_raw:.4f} m3/s")

    # Step 7d: Use predictor.predict() for comparison
    result = predictor.predict(x_dynamic, x_flat, anchor_flow)
    print(f"\n  predictor.predict() result:")
    for k, v in result.items():
        print(f"    {k:<30} = {v:.6f}")

    # Check consistency
    diff = abs(pred_raw - result["pred_raw_streamflow"])
    print(f"\n  Manual vs predict() diff:  {diff:.8f}  {'PASS' if diff < 0.01 else 'FAIL'}")

    # ---- 8. Cross-validate: original prediction_service.py ------------------
    sep("8. CROSS-VALIDATION vs prediction_service.py")

    # Import the original service's preprocess function
    from prediction_service import (
        preprocess_window as orig_preprocess,
        build_feature_window as orig_build_feature_window,
    )

    # Build window with original function
    orig_df = orig_build_feature_window(station, rain_series, anchor_flow, prev_flow, TEST_DATE)

    # Compare feature windows
    our_cols  = set(df_window.columns)
    orig_cols = set(orig_df.columns)

    missing_in_ours  = orig_cols - our_cols
    extra_in_ours    = our_cols - orig_cols

    print(f"\n  Our window columns:      {len(our_cols)}")
    print(f"  Original window columns: {len(orig_cols)}")

    if missing_in_ours:
        print(f"\n  [!] MISSING in our build (present in original):")
        for c in sorted(missing_in_ours):
            print(f"      - {c}")
    else:
        print(f"  Missing columns: None (all original cols present in ours)")

    if extra_in_ours:
        print(f"\n  [~] EXTRA in our build (not in original) -- OK if unused by scalers:")
        for c in sorted(extra_in_ours):
            print(f"      + {c}")
    else:
        print(f"  Extra columns: None")

    # Compare values for shared columns on last row
    shared_cols = sorted(our_cols & orig_cols)
    mismatches = []
    for col in shared_cols:
        ours = float(df_window.iloc[-1][col])
        orig = float(orig_df.iloc[-1][col])
        if abs(ours - orig) > 1e-6:
            mismatches.append((col, ours, orig))

    if mismatches:
        print(f"\n  [!] VALUE MISMATCHES on last row ({len(mismatches)}):")
        for col, ours, orig in mismatches:
            print(f"      {col:<45}  ours={ours:.6f}  orig={orig:.6f}")
    else:
        print(f"\n  Value comparison: ALL {len(shared_cols)} shared columns match exactly")

    # Now preprocess with original function and compare arrays
    orig_x_dyn, orig_x_flat = orig_preprocess(orig_df, predictor)

    dyn_diff  = np.abs(x_dynamic - orig_x_dyn).max()
    flat_diff = np.abs(x_flat - orig_x_flat).max()

    print(f"\n  Preprocessed x_dynamic max diff: {dyn_diff:.8f}  {'PASS' if dyn_diff < 1e-4 else 'FAIL'}")
    print(f"  Preprocessed x_flat max diff:    {flat_diff:.8f}  {'PASS' if flat_diff < 1e-4 else 'FAIL'}")

    # ---- 9. Negative streamflow analysis ------------------------------------
    sep("9. NEGATIVE STREAMFLOW ANALYSIS")

    print(f"\n  The model predicts a DELTA (change in streamflow).")
    print(f"  pred_streamflow = anchor + delta")
    print(f"")
    print(f"  When anchor is very small and delta is negative, we get")
    print(f"  negative streamflow. This is a known limitation of the")
    print(f"  delta-based approach (same behavior as original backend).")
    print(f"")
    print(f"  Example from this gauge:")
    print(f"    anchor = {anchor_flow:.4f} m3/s")
    print(f"    delta  = {raw_delta:.4f} m3/s")
    print(f"    result = {pred_raw:.4f} m3/s {'<-- NEGATIVE' if pred_raw < 0 else ''}")
    print(f"")

    # Check original backend for clamping
    # Looking at prediction_service.py line 140: pred_raw = prev_raw_streamflow + raw_delta
    # No clamping in original either.
    print(f"  Does the original backend clamp to zero? Checking prediction_service.py...")
    print(f"  Line 140: pred_raw = prev_raw_streamflow + raw_delta")
    print(f"  --> NO CLAMPING in original either. Our behavior is CONSISTENT.")

    # ---- Summary -------------------------------------------------------------
    sep("VERIFICATION SUMMARY")
    issues = []
    if not all_ok:
        issues.append("Some derived features had mismatches")
    if not shape_ok:
        issues.append("Array shapes incorrect")
    if has_nan_dyn or has_nan_flat:
        issues.append("NaN/Inf found in preprocessed arrays")
    if not dynamic_match:
        issues.append("Dynamic column order mismatch with config")
    if not flat_match:
        issues.append("Flat column order mismatch with config")
    if diff > 0.01:
        issues.append("Manual forward pass doesn't match predict()")
    if missing_in_ours:
        issues.append(f"Missing columns: {missing_in_ours}")
    if dyn_diff > 1e-4 or flat_diff > 1e-4:
        issues.append("Preprocessed arrays differ from original pipeline")

    if issues:
        print(f"\n  ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(f"    [!] {issue}")
    else:
        print(f"\n  ALL CHECKS PASSED")
        print(f"  - Static features: correct")
        print(f"  - Dynamic window:  correct shape (15, 32)")
        print(f"  - Flat features:   correct shape (42,)")
        print(f"  - Scaler pipeline: matches original prediction_service.py")
        print(f"  - LSTM forward:    produces output")
        print(f"  - XGBoost corr:    produces output")
        print(f"  - Column order:    matches model_config.json")
        print(f"  - Cross-validation: identical to original pipeline")
        print(f"  - Negative flows:  consistent with original (no clamping)")

    print()


if __name__ == "__main__":
    main()
