# STATE

- Milestone: v2-prod-harden
- Commits: a8c30b6 (Phase 01), e293b12 (ops+trust units), 5ba13e1 (briefing core), + quality flags (this session).
- Verified this window: baseflow --help/--list-coords/--from-csv (367 stations, sync JSON ready); migration 002 idempotent; alerts router live (fastapi present); version stamp (model hybrid-lstm-xgb-32d-256h-835c1591, db_date 2026-07-14); briefing paragraph; quality rules+DB; tsc EXIT 0; backend imports to torch boundary.
- Env: pandas/fastapi/httpx/apscheduler/requests/sklearn/joblib installed; torch+xgboost deferred (heavy, Render has them).
- DB: prod 378 rows pre-reseed (fresh seed → 367 stable IDs). No writes to prod DB this window (temp DBs only).

## HELD (genuinely need user — moved on per instruction, nothing blocked code-wise)
1. Live GloFAS download: needs CDS_API_KEY env (or ~/.cdsapirc). Module ready; run `PYTHONPATH=backend python -m Flood_prediction.baseflow_glofas` then POST sync JSON to /api/admin/sync-streamflow.
2. Torch inference smoke (`validate.py` sample_io + /predict): needs torch+xgboost install (~1GB, >window). Render has them; or approve heavy pip install next session.
3. Frontend modal upgrade (briefing paragraph + copy/download), anchor-aware base/target, scenario control + p10/p90 band + persistence baseline: tsc green, but visual/product decisions — held for your return.
4. Percentile fill from residuals: no npz in repo; reconstruct offline in colab from frozen predictor over test split per regime, then load via update_flow_percentiles.
5. Delivery wiring: version stamp + alerts into /predict, dummy vs real API separation, ProjectDetail live page — touches main.py (rewrite budget: already 3 patches, next change should be rewrite to routers).

## Next on your return
Say which to take first (suggest: CDS key → live anchor → reseed 367 → torch smoke → frontend modal). No questions asked during 20-min window per instruction.
