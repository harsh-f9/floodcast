# FloodCast v2-prod-harden — PROJECT.md

## Goal
Migratable production hardening of UP flood forecasting platform, not stitch-fixes.
Research stays as batch lineage doc; production consumes frozen curated output.

## Non-goals (hard constraints)
- Do NOT re-run 3.2M-row v1→v14 chain on Render or live GCS zarr streaming (90GB reforecast + 66GB reanalysis).
- Do NOT touch `C:\CRO\CRO` (dead 2-byte `.pt` pointer). Canonical model is `crowebsite/backend/Flood_prediction/deploy/` (3.3MB real).
- Do NOT invent embankment data. Proxy assets only: DIST_SINK, UP_AREA, slp, urb_pc, attenuation, velocity.
- Do NOT promise per-0.25° rainfall, dam inputs, Earth Engine live feed, Kaggle publish, GloFAS, SAR/DEM shipped.

## Canonical locations
- Git root: `crowebsite/` (contains `backend/`, `src/`, `api/`, `vercel.json`)
- Research lineage: `../colab/` (outer, 18 notebooks) + `../colab/PIPELINE_DATA_PROCESSING.md`
- Resume context: `../Flood_Resume_Context.md`
- Deploy contract: `backend/Flood_prediction/deploy/{best_flood_lstm.pt,flood_xgb_corrector.json,yj_transformer.pkl,mm_scaler.pkl,feature_scaler.pkl,target_scaler.pkl,model_config.json,flood_lstm.py,predictor.py,sample_io.json,gauges_info.csv,discharge_1007.csv}`
- DB: `backend/Flood_prediction/database.py` → `flood_prediction.db` (4 tables)
- Inference: `backend/Flood_prediction/prediction_service.py` → `deploy/predictor.py` singleton
- API: `backend/main.py` (`/predict` real hybrid vs `/api/predict` dummy randomized) + `api/index.py` + `vercel.json`
- Frontend: `src/pages/FloodDashboard.tsx` (1661 lines) + `src/pages/ProjectDetail.tsx`
- Ops: `backend/Flood_prediction/scheduler.py` (6AM IST cron, currently early-return DISABLED), `local_bootstrap.py` (laptop push), `backend/main.py:345-377` admin sync (no auth)

## Standards (migration-safe)
- DB: versioned migrations `backend/Flood_prediction/migrations/NNN_*.py`, never ALTER by hand. Backfill defaults.
- Contract: freeze `gauges_info.csv + model_config.json + sample_io.json` as SCHEMA.md. Validate on seed + sync.
- API: stamp `model_version + db_date + generation_id` on every `/predict`.
- Config: env vars for webhook/cron/auth. No hardcoded dates/passwords. `DRY_RUN` flag for scheduler.
- Rewrite rule: patch if additive/isolated; rewrite module if >2 patches touch same file or logic duplicated. Candidates: `database.py`, `prediction_service.py`, `FloodDashboard.tsx` → split to `db/migrations/`, `services/inference.py`, `components/Map|Chart|Briefing/`.
- Docs: per-phase `SPEC.md → PLAN.md → VERIFICATION.md` + `onboarding/SUMMARY.md`. No code without plan + verification.
- Gates: `code-review` always, `ui-review` for dashboard, `secure-phase` for webhook/auth.
