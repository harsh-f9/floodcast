# Phase 01-freeze-contract — PLAN.md

## Tasks
1. SCHEMA.md (contract freeze): from `deploy/gauges_info.csv` (19 cols incl 2 Unnamed, 378 rows), `model_config.json` (32 dyn / 42 flat / 10 static, SEQ_LEN 15, target mean 0.0108 scale 144.7006), `sample_io.json` (3 samples, x_dyn 15×32, x_flat 42). Quote pipeline §8: 3,213,819=367×8757, 52-55 cols, _yj suffix rule (8 raw→_yj), 11-gauge gap list. Station master: `hybas_to_gauge_mapping.csv` + `gauge_locations_enriched.json` (hybas_* ↔ station_id index ↔ district).
2. Migrations infra: `backend/Flood_prediction/migrations/__init__.py` + `runner.py` (applies versioned `NNN_*.py`, tracks `schema_migrations` table) + `001_baseline.py` (documents 4-table baseline, no-op) + README. No ALTER yet.
3. Validation module: `backend/Flood_prediction/validation.py` (~40 lines): `validate_station_row()`, `validate_rainfall()`, `validate_streamflow()` — asserts required cols, rp_20>rp_15>rp_5>rp_2>0, lat 23.5-31.0 lon 77-85, date ISO, rainfall 0-500, flow >=0. Wire into `seed_db.py` (fail-fast per row) + `main.py` admin sync (400 on bad input).
4. Verification: `python -m Flood_prediction.validate` (sample_io diff<0.5 if torch available, else schema-only), `python -c "import validation; ..."` asserts, `seed` dry-run on temp DB.

## No-code-without-plan gate
- This PLAN is the gate. Code must match SPEC verification criteria.

## Rewrite check
- Patch, not rewrite: additive files only (SCHEMA, migrations/, validation.py) + minimal edits to seed_db/main. database.py / prediction_service.py untouched (rewrite deferred to Phase 02 if >2 patches).
