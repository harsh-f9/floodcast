# Baseflow outputs — deploy/baseflow/

Automated anchor for future predictions. See `../baseflow_glofas.py` (migratable, delete file+dir to remove).

## Workflow (previous date IST)
1. `PYTHONPATH=backend python -m Flood_prediction.baseflow_glofas` → downloads GloFAS intermediate for yesterday IST (needs CDS_API_KEY or ~/.cdsapirc).
2. Manual fallback (user's Copernicus workflow): download GRIB via CDS website → place extracted CSV → `python -m Flood_prediction.baseflow_glofas --from-csv <csv> --date YYYY-MM-DD`.
3. `POST deploy/baseflow/sync_streamflow_YYYY-MM-DD.json` to `/api/admin/sync-streamflow` (validates date ISO + flow>=0, 400 on bad). This anchors `gauge_state`; `/predict` chains forward day-by-day.
4. Anchor-aware UI (Phase 03): base = max(gauge_state.date) fallback 2026-07-14; target = base+7. Never fabricate 0.0 for missing (NaN/negative skipped).

## Files
- `extracted_streamflow_YYYY_MM_DD.csv`: audit (gauge_id,latitude,longitude,streamflow_m3s), colab naming.
- `sync_streamflow_YYYY-MM-DD.json`: `{station_id: {date: flow}}`, 367 stations (EXCLUDED_11 skipped, stable IDs = deploy order index).

## Latency (verified 2026-09-25)
GloFAS intermediate publishes with ~2-day lag: on Sep 25, Sep 24 AND Sep 23 both
400 (`invalid request`), Sep 22 succeeds. Default run auto-steps back up to
`--lookback 7` days and anchors on latest-published date. Filenames always carry
the actual anchor date (not the requested one).

## Anchoring
- Local dev: direct insert via `database.insert_gauge_state` after `validation.py`
  checks (backend can't boot locally without torch; endpoint path preferred where live).
- Render prod: `POST sync JSON to /api/admin/sync-streamflow` (validates 400 on bad),
  then `/predict` chains forward. Prod DB untouched by local runs.

## Example (verified 2026-09-25)
`extracted_streamflow_2026_09_22.csv` (378→367) + `sync_streamflow_2026-09-22.json` (367 stations) from `downloading base streamflow data/extracted_streamflow_2026_09_22.csv`.
