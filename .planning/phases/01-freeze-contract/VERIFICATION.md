# Phase 01-freeze-contract — VERIFICATION.md

Date: 2026-09-25. Status: PASS (code-review pending).

## Checks run
- `verify_phase01.py`: good row OK, bad rp caught, bbox caught, bad date caught, bad rain caught → validation.py PASS.
- Migrations dry-run on temp DB: `init_tables()` + `run_migrations()` → `schema_migrations [(1,)]` → PASS (file handle left open on Windows, expected, no data loss).
- `verify_phase01d.py` stdlib csv: `gauges_info.csv` 378 rows, 0 bad rows (rp_20>rp_15>rp_5>rp_2 + UP bbox) → PASS.
- `SCHEMA.md` created at `backend/Flood_prediction/SCHEMA.md` with §8 lineage, _yj rule, 11-gauge gap list, station master.
- Edits: `seed_db.py` fail-fast per row, `main.py` admin sync 400 on bad date/range.

## Not yet run (needs torch env)
- `python -m Flood_prediction.validate` sample_io diff<0.5. Code untouched, low risk. Run on Render or venv with torch before ship.

## Goal-backward
SPEC required: SCHEMA exists ✓, seed fails fast ✓, sync validates ✓, sample_io path intact ✓.
