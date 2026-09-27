# Phase 07-prediction-backfill-guarantee — PLAN.md

## Diagnosis (grounded 2026-09-27)

- D1 Split gap logic: `run_prediction_for_station` loops `last→target`; `predict_future_streamflow` loops `last→today` + `today+1→target`. No shared helper; `client_rainfall` ignored in both backfill loops; batch-only rainfall with `.get(...,0.0)` silent zero.
- D2 Wrong clock: service + `/predict` branch use system `date.today()`; chat stack uses `today_ist()` (IST + `client_today` override). Laptop-vs-Render wall-clock can disagree.
- D3 Past-target hole: `predict_future_streamflow(target<=today)` backfills through today but returns empty `trajectory`; `run_prediction_for_station(target<=today)` never fills `target+1..today`.
- D4 Agent masking: `tools._anchor_and_target` substitutes `anchor+horizon` for out-of-window explicit dates (correct) but the fallback flag path is the only signal; in-window explicit past dates must reach the service verbatim.
- D5 Provenance gap: `insert_rainfall` is `INSERT OR IGNORE` (first writer wins); `insert_gauge_state` is `REPLACE`; neither records how rainfall was obtained.

## Design decisions

1. **Shared helper in `prediction_service.py`**: `ensure_anchor_to_today(station, rain_series, last_date, last_raw, prev_raw, today, client_rainfall, source) -> (last_raw, prev_raw, backfilled: list[dict{date, rainfall_mm, rainfall_source}])`. Owns the per-date loop: for each `d in last_date+1..today`: skip-if-flow-row-exists (read rainfall source from DB, still advance chain + record source `db`), else resolve rainfall → persist → window → predict → persist. Returns updated chain state + audit list.
2. **Per-date rainfall resolver** `_resolve_rainfall_for_date(station, date_str, client_rainfall, batch_cache)`: order `client` → `live` (`fetch_rainfall_mm` single-day attempt) → `batch` (pre-fetched range value if present) → `db` (stored row) → `fallback-zero`. Returns `(value, source)`. "Always live" = live is attempted every date (user decision); fallbacks only on exception/None.
3. **Clock**: service gets `_today_ist()`: try `chat_agent.clock.today_ist`, except → `datetime.now(IST)` with fixed +5:30, except → `date.today()`. `main.py /predict` uses the same resolver for its past/future branch (import with fallback, no hard dependency on chat package).
4. **Rewiring**:
   - `run_prediction_for_station`: compute `today=_today_ist()`; call `ensure_anchor_to_today` for `last_date+1..min(today, ...)` ALWAYS (even when target<=today → full gap to today); then if `target<=today` read target row from DB and answer; else continue `max(today,last)+1..target` with the same per-date resolver+chain (this preserves its current future behavior, now with audit + client-aware rainfall).
   - `predict_future_streamflow`: same helper for `last→today`; then `today+1..target` loop kept, but rainfall resolution upgraded to `_resolve_rainfall_for_date`; past-target returns answer-from-DB instead of empty trajectory (include `trajectory: []` + target prediction fields for backward compat, plus `backfilled_dates`).
   - Response additive fields: `backfilled_dates: [str]`, `backfilled: [{date, rainfall_mm, rainfall_source}]`. Existing keys untouched.
5. **Existing-row rule** (per Prohibition): revisiting a date with a stored flow row never overwrites it; chain advances with the stored value, rainfall source recorded as `db` (or `client` if override supplied AND no stored rainfall? rainfall table is IGNORE — first writer wins, so client override only applies when no stored rainfall row; document in LEARNINGS).
6. **Agent**: `_anchor_and_target` keeps the 30-day window rule; verify in-window explicit dates pass through verbatim (fix only if test proves masking; current code already passes in-window dates — test locks it).

## Tasks (each: implement → targeted test → run suite slice)

1. `prediction_service.py`: add `_today_ist()`, `_resolve_rainfall_for_date()`, `ensure_anchor_to_today()`; rewire both public functions; additive response fields. No signature breaks (new optional params only).
2. `backend/main.py`: IST-based `/predict` branch via shared resolver (local import with fallback).
3. `backend/chat_agent/tools.py`: only if test shows masking — otherwise no change, test locks passthrough.
4. Tests — new `backend/Flood_prediction/tests/test_backfill_guarantee.py` (fake DB layer via monkeypatched `database` module functions + stub predictor + stub rainfall): gap-created-before-target; per-date live call count + chaining; past-target answered with full gap; fallback-zero flagged; in-window explicit target passthrough; empty-gap no-op.
5. Regression: full `backend/chat_agent/tests` suite + new tests green; `tsc` untouched (no frontend changes).
6. Docs: `STATE.md` append; phase `LEARNINGS.md` (new file only); `VERIFICATION.md` with evidence.

## Test doubles strategy

- Monkeypatch `prediction_service.fetch_rainfall_mm` (count calls per date), `fetch_rainfall_batch` (return partial map to force fallback paths), `get_predictor` (stub with `predict()` returning deterministic delta), and the `database` module functions (`get_station`, `get_rainfall_history`, `get_gauge_state`, `insert_rainfall`, `insert_gauge_state`, `get_rainfall_for_date`, `query_one`) with in-memory fakes. No live HTTP, no torch, no real DB file.

## Rewrite check

Patch stays inside `prediction_service.py` (+2 small call-site touches). If the helper exceeds ~120 lines or a third caller needs it, split to `services/backfill.py` per PROJECT.md rewrite rule — not now.

## No-code-without-plan gate

- This PLAN is the gate. Every task maps to SPEC R1–R5 and its Acceptance Criteria.
