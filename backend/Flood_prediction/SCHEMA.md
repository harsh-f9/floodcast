# Frozen Deploy Contract — SCHEMA.md (Phase 01)

Source: `colab/PIPELINE_DATA_PROCESSING.md` §§0,8 + live `deploy/` artifacts. Research stays batch; prod consumes this.

## 1. Canonical artifacts (do not re-run)
- `backend/Flood_prediction/deploy/gauges_info.csv` — 378 rows + header (379 lines), 19 cols: `Unnamed:0.1,Unnamed:0,gauge_id,slp_dg,slp_dg_uav,for_pc,urb_pc,attenuation_factor,flow_velocity_km_per_day,upstream_lag1_days,upstream_lag2_days,rp_2,rp_5,rp_15,rp_20,latitude,longitude,UP_AREA,DIST_SINK`. Example `hybas_4120789590` Bijnor 29.252083N 78.66875E, RP2 722.99 RP5 972.56 RP15 1213.02 RP20 1271.20, UP_AREA 5040 DIST_SINK 2064.8.
- `backend/Flood_prediction/deploy/model_config.json` — LSTM `input_size 32 hidden 256 layers 2 dropout 0.2 seq_len 15`; `dynamic_cols[32]` / `flat_cols[42]` / `static_cols[10]`; scalers: YJ 8 raw→_yj, MM 10 cols, Standard ~15 cols, target `mean 0.0108 scale 144.7006`. Inference: YJ→MM→Standard → LSTM+XGB → inverse → prev+delta.
- `backend/Flood_prediction/deploy/sample_io.json` — 3 samples, `x_dynamic 15×32`, `x_flat 42`, `y_delta_scaled`, `y_raw_streamflow`, `pred_raw_streamflow`. `validate.py` asserts diff<0.5.
- Model binaries: `best_flood_lstm.pt` 3.3MB real, `flood_xgb_corrector.json` ~1.2MB, 4×`.pkl`. Dead pointer: `C:/CRO/CRO/.../best_flood_lstm.pt` 2 bytes — never cite.

## 2. Panel lineage (§8)
`processed_hydrology_data.csv` = 3,213,819 rows = 367 gauges × 8,757 days (2000-01-02→2023-12-23), ~52-55 cols. Row logic: 3,214,186 − 3,213,819 = 367 = one row/station dropped for `streamflow_delta` shift. Train 2000-01-02→2019-03-08 / test 2019-03-08→2023-12-23. Target `streamflow_delta`, state `prev_raw_streamflow`.

## 3. _yj suffix rule (EDA-5 forensics)
8 cols YJ-transformed, renamed raw→_yj: `UP_AREA, rain_basin_size_interaction, uparea_upstream_rain_interaction, rain_slope_interaction, rain_urban_interaction, rain_monthly_swc_interaction, upstream_rain_mean, weighted_upstream_rain` → `*_yj`. Not duplicates — keep mapping when joining inverse vs v4 vs Kaggle copies.

## 4. 378→367 gap (11 gauges in v6/rainfall but not model panel)
`hybas_4121486100, hybas_4120878420, hybas_4120888940, hybas_4121472500, hybas_4120878430, hybas_4120888130, hybas_4120881440, hybas_4120854010, hybas_4121445720, hybas_4120889880, hybas_4120855950`. Deploy `gauges_info.csv` still seeds 378; model trained on 367. Prod serves deploy set; document, don't silently drop.

## 5. Station master
- `crowebsite/hybas_to_gauge_mapping.csv` (1624 lines incl header: `Hybas_ID,Lat,Long,Gauge_ID,Gauge_Lat,Gauge_Long`) + `crowebsite/gauge_locations_enriched.json` (`gauge_id,latitude,longitude,location_name,sub_district,district,state,country`) = string `hybas_*` ↔ int `station_id` (row index in `seed_db.py:40-41`) ↔ district. No new entity-resolution.

## 6. Validation rules (enforced in `validation.py`)
Required cols, `rp_20>rp_15>rp_5>rp_2>0`, lat 23.5-31.0 lon 77-85 (UP bbox), date ISO, rainfall 0-500mm, flow >=0. Fail-fast on seed/sync.
