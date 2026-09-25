# Exhaustive verify — 2026-09-25 (no commits)

## Backend (subagent, read-only)
- py_compile 21 files: PASS
- imports: database/validation/migrations PASS; main FAIL (no fastapi), seed_db FAIL (no pandas), prediction_service FAIL (no pandas), predictor FAIL (no torch). Cause: system python 3.13 bare; `.venv` broken (points to anaconda), `.venv_linux` broken symlink. Need env fix before live inference test.
- DB exists: `Flood_prediction/flood_prediction.db` 1.3M; station_static 378, gauge_state 1890 (2026-07-10→14), rainfall 22944 (2026-05-15→07-14). `/stations` docstring says 367 — stale vs 378 actual.
- deploy/ PASS: 3.3MB pt, 4 pkls, model_config (32/256/2/0.2/15), sample_io 3 samples, gauges 378 rows, discharge 378 rows, xgb 1.18MB.
- Anchors diverged FAIL: seed 2026-07-10 vs bootstrap 2026-07-11 vs local_bootstrap 2026-07-16. User note: July 14 base = only day with Copernicus actuals, then chained; no live Copernicus pipeline (manual CSV convert). So today-switch unsafe — use anchor-aware base (max gauge_state date, fallback July 14).
- Admin auth FAIL (open, no Depends, placeholder API_KEY unused). Deferred to Phase 05 (Telegram bot chosen).

## Frontend (subagent, read-only)
- scripts/node_modules PASS; no test/typecheck script.
- Hardcoded dates FAIL (8 hits: 238,251,261,330,344,354,420 + comment 411, shortcut 860). Single-station runPrediction dynamic PASS.
- cro gate FAIL (317-321 prompt=="cro", district path ungated). Approved: remove → confirm + rate-limit.
- getRiskStatus PASS; real/dummy separated PASS; vercel PASS with SPA-fallback gap + absolute API_BASE bypass.
- enriched 378 entries PASS but NOT UP-only: includes Haryana/Bihar/MP (Faridabad,Karnal,Buxar,Ashoknagar,Morena,Shivpuri,Chhatarpur,Niwari). 71 districts total, 63 UP.
- tsc FAIL 4 errors: Station missing rp_2/5/15/20 (179-182 fallback). Fix type before build.

## Decisions from user 2026-09-25
- Alerts: Telegram bot (BOT_TOKEN+CHAT_ID env).
- Dates: keep anchor-aware, do not blind today-switch (Copernicus manual).
- cro gate: remove approved.
- Stations: filter to 367 trained (11-gauge denylist).
- Commits: only after exhaustive verify (this doc). No commits yet.
