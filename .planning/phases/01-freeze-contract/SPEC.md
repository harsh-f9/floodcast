# Phase 01-freeze-contract — SPEC.md

## Goal
Freeze chaos, don't re-run it. Promote deploy artifacts as versioned contract.

## Scope
- Freeze: `backend/Flood_prediction/deploy/gauges_info.csv` + `model_config.json` + `sample_io.json` as contract. Add `SCHEMA.md` quoting pipeline §8 (367×8757, 52-55 cols, _yj suffix rule, 11-gauge 378→367 gap list from EDA-5).
- Station master: `hybas_to_gauge_mapping.csv` + `gauge_locations_enriched.json` as hybas_* ↔ int station_id ↔ district map. No new entity-resolution.
- Validation: lightweight asserts in `seed_db.py` + `/api/admin/sync-*` (required cols, date parse, rp_20>rp_15>rp_5>rp_2, lat/lon in UP bbox 23.5-31N/77-85E). 30 lines asserts, not Great Expectations.
- Migrations infra: `backend/Flood_prediction/migrations/` + runner, no functional migration yet (prepares Phase 02).

## Non-goals
- No re-run of v1→v14 chain on Render. No live GCS zarr streaming.
- No schema rewrite. No percentile fill (Phase 02).

## Verification criteria
- `SCHEMA.md` exists, cites row-count logic 3,214,186-3,213,819=367, lists 11 missing gauges, _yj mapping.
- `seed_db.py` fails fast on bad rp ordering / out-of-bbox / missing cols.
- `/api/admin/sync-*` validates date ISO + float range before insert.
- `python -m Flood_prediction.validate` still passes sample_io (diff<0.5).
- code-review passes.
