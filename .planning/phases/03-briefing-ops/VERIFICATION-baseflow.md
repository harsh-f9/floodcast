# Baseflow automation — VERIFICATION.md (Phase 03 ops part)

Date: 2026-09-25. Status: PASS (download path needs CDS key; conversion path verified).

## Source found
- `crowebsite/downloading base streamflow data/script used in colab to download for 22 sept.py` (GloFAS cems-glofas-historical v4.0 lisflood intermediate, bbox from final_gauges_data_temp.csv latitude_x/longitude_x).
- `dataset_final_temp` = final_gauges_data_temp.csv (gauge lat/long list). Prod equivalent: `backend/Flood_prediction/deploy/gauges_info.csv` (frozen contract, 378 rows) — used as coord source.
- Example output: `extracted_streamflow_2026_09_22.csv` (379 lines, cols gauge_id,latitude_x,longitude_x,...,streamflow_m3s).

## New module (migratable)
- `backend/Flood_prediction/baseflow_glofas.py`: stdlib-only import (tz fallback for Windows), lazy pandas/xarray/cdsapi, env CDS_API_KEY, yesterday-IST default, --from-csv manual path, stable station_ids, EXCLUDED_11 skip, NaN/negative skipped (never fabricate 0.0).
- Outputs: `deploy/baseflow/extracted_streamflow_YYYY_MM_DD.csv` + `sync_streamflow_YYYY-MM-DD.json` + README.md.

## Checks
- COMPILE_OK; --help OK; --list-coords: 367 gauges, bbox N30.0271 S24.0271 E84.5938 W77.0396, target 2026-09-24 (yesterday IST) OK.
- --from-csv on 2026_09_22 file: audit CSV + sync JSON with 367 stations, keys 0/1/2 sample flows 0.1875/1063.38/194.64 OK. Ready to POST to /api/admin/sync-streamflow to anchor predictions.
- Live download NOT run (no CDS key in session). Next: set CDS_API_KEY, run for yesterday, POST sync JSON, verify /predict chains.

## Live run 2026-09-25 (CDS key configured)
- `--date 2026-09-24` → CDS 400 invalid (not published); `--date 2026-09-22` → success (35.5k zip, 367 stations, flows 0.015–17322 m3/s). Latency ~2 days confirmed.
- `--lookback 3` default run: 24th 400 → step back → 23rd 400 → step back → 22nd success. Filenames carry actual anchor date.
- Local dev DB anchored: 367 rows 2026-09-22 via validated direct insert (max gauge_state 2026-07-14 → 2026-09-22). Prod Render DB untouched — POST sync JSON there on deploy.
