# Phase 07-prediction-backfill-guarantee — VERIFICATION.md

**Verified:** 2026-09-27
**Method:** unit tests with in-memory fakes (no live HTTP, no torch, no real DB) + full suite regression + import checks.

## Acceptance criteria — result

- [x] Anchor 09-22 → today 09-27 → target 09-29 via EITHER service function persists gap rows 09-23..09-27 before 09-28/29 rows
  - `test_run_prediction_fills_gap_before_target`: gauge contains 23..29; 29 == 170.0 via +10 chain from 100.0 anchor. PASS
  - `test_predict_future_future_target_covers_gap_then_trajectory`: trajectory == [28, 29], first anchored at 150.0; 5 backfilled dates. PASS
- [x] Per-date live rainfall attempt once per gap date, `build_feature_window` once per gap date, chaining verified
  - `live_calls == [23,24,25,26,27,28,29]` (7 singles, no batch); `window_calls == live_calls + [target-debug-rebuild]`; `stub.prevs == [100..160]` (N+1 input == N output). PASS
- [x] Target 09-25 (past) returns the 09-25 prediction with no empty-trajectory success; gap rows 09-23..09-27 exist
  - `test_predict_future_past_target_answered_from_backfill`: pred 130.0, anchor 120.0, delta 10.0, trajectory [] but explicit target fields present. PASS
- [x] Response carries `backfilled_dates`; forced live-failure persists flagged `fallback-zero`
  - `test_live_429_breaker_falls_back_with_provenance`: 1 live attempt then 429 breaker, 1 lazy batch, both dates `fallback-zero`, flow still chained (120.0). PASS
- [x] Explicit in-window past `target_date` reaches the model unchanged; `/predict` branch follows IST today
  - `AgentTargetPassthroughTest` (2 tests, real dev DB): anchor+3d verbatim, fallback False; anchor+40d fallback True. PASS
  - `backend/main.py::predict_flood` branches on `_today_ist()` (source-inspected + module imports cleanly). PASS
- [x] Full existing backend suite green + new tests green
  - `python -m unittest discover -s backend/chat_agent/tests`: **169 tests, OK** (158 pre-existing + 11 new). No regressions.
- [x] `STATE.md` updated; phase `LEARNINGS.md` written; no prior phase `LEARNINGS.md` modified (verified: only `phases/07-*/LEARNINGS.md` created).

## Extra behavior locked by tests

- `test_existing_rows_never_rewritten`: stored rows keep values; past target still backfills through today (24..27 from anchor 23).
- `test_client_rainfall_shortcircuits_live_per_date`: per-date client override, no live call for covered dates.
- `test_empty_gap_is_noop`: anchor == today → `backfilled_dates == []`, extension only.
- `test_future_row_reused_not_recomputed` + `test_anchor_at_future_row_extends_from_it`: reuse/no-rewrite rule; future stored row becomes anchor.

## Known limitations (not failures)

1. Anchor = latest persisted row of any source (forecast rows count). Observed-only anchor is a possible follow-up; current semantics documented in LEARNINGS.
2. Open-Meteo forecast endpoint still backs live calls (no archive API); dates outside its window resolve via batch → db → flagged `fallback-zero`.
3. `sync_historical_predictions` untouched (disabled push-model path, out of scope).

## Files changed

- `backend/Flood_prediction/prediction_service.py`: `_today_ist`, `_fetch_live_rainfall_or_raise`, `_resolve_rainfall_for_date`, `_step_single_date`, `ensure_anchor_to_today`; both public functions rewired; additive `backfilled_dates`/`backfilled` (+ target/anchor/delta on future path).
- `backend/main.py`: `/predict` past/future branch on IST.
- `backend/chat_agent/tests/test_backfill_guarantee.py`: 11 tests (new file).
- `.planning/`: `phases/07-prediction-backfill-guarantee/{SPEC,PLAN,VERIFICATION,LEARNINGS}.md`, `STATE.md`, `ROADMAP.md`.
- `backend/chat_agent/tools.py`: unchanged (verified passthrough already correct).
