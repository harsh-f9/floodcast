# Phase 07: prediction-backfill-guarantee — Specification

**Created:** 2026-09-27
**Ambiguity score:** 0.12 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Every prediction call (agent tool or user `POST /predict`) for a target date first sequentially computes and persists streamflow for all dates in the anchor→today gap, resolving live dynamic features (rainfall per date + feature window + chained model state) for each gap date before answering the target.

## Background

- Anchor today is the CDS baseflow download date (currently 2026-09-22): the latest observed `gauge_state` row per station. `today` is the day the code runs (Indian laptop via Render URL, or Render prod) — must resolve to Asia/Kolkata, honoring the chat `client_today` override where present.
- `prediction_service.run_prediction_for_station` fills `last→target` with one batch rainfall fetch and silent `0.0` fallback, and ignores `client_rainfall` in the gap loop.
- `prediction_service.predict_future_streamflow` fills `last→today` then `today+1→target`, but uses system `date.today()` (not IST), one batch fetch with silent `0.0` fallback, ignores `client_rainfall` in backfill, and returns an empty trajectory when `target <= today`.
- `backend/main.py POST /predict` branches past/future on system `date.today()`.
- Chat-agent tools (`predict_station`, `predict_district`, `sweep_stations` → `_forecast_one_station` → `_predict_one` → `predict_future_streamflow`) derive anchor as latest `gauge_state` row (including forecast rows) and never explicitly guarantee the anchor→today gap with per-date live features.
- User decisions locked 2026-09-27: anchor = CDS download date (22 Sept, latest observed row); today = simplest portable "current time whichever day it runs" (IST); rainfall = always attempt live per date; past targets = backfill anchor→today first, then extend/answer target.

## Requirements

1. **Guaranteed anchor→today backfill on every prediction path**
   - Current: gap handling differs per entry point; past-target calls can leave the anchor→today tail unfilled; agent and API paths duplicate logic.
   - Target: one shared helper (e.g. `ensure_backfilled(station, today)`) owns the gap loop; `run_prediction_for_station` AND `predict_future_streamflow` both call it first; `POST /predict` and all agent forecast tools reach the target only through these two functions.
   - Acceptance: with anchor 2026-09-22 and fake today 2026-09-27, calling either service function for target 2026-09-29 leaves persisted `gauge_state` rows for 09-23..09-27 before any 09-28/29 rows are written.

2. **Per-date live dynamic features with chaining**
   - Current: single `fetch_rainfall_batch(start,end)` for the whole range; missing dates become `0.0` via `.get(..., 0.0)`; `build_feature_window` is per-date but rainfall input is batch-cached.
   - Target: for EACH gap date in order: rainfall = `client_rainfall[date]` if supplied, else a live per-date attempt (`fetch_rainfall_mm` or equivalent single-day Open-Meteo call); on live failure fall back to batch value → stored DB value → `0.0` (explicitly recorded). Then `build_feature_window` → `preprocess_window` → `predictor.predict` with chained `last_raw/prev_raw` carried forward; `insert_rainfall` + `insert_gauge_state` persisted per date; in-memory `rain_series` updated per date so the next date's rolling features see it.
   - Acceptance: unit test with mocked rainfall/model asserts the per-date fetch is invoked once per gap date (not once total), `build_feature_window` invoked once per gap date, and the `prev_raw` passed to date N+1 equals the prediction written for date N.

3. **Past-target semantics (backfill then extend)**
   - Current: `predict_future_streamflow` with `target <= today` backfills through today then returns an empty `trajectory`; `run_prediction_for_station` stops at `target` and never fills `target+1..today`.
   - Target: any call with `target <= today` still backfills the full anchor→today gap, then answers the target date from the now-persisted rows (same response shape as today, no empty-trajectory success). Calls with `target > today` backfill anchor→today then compute `today+1..target` sequentially with the same per-date feature pipeline.
   - Acceptance: anchor 09-22, today 09-27, target 09-25 → response carries the 09-25 prediction AND `gauge_state` contains 09-23..09-27; target 09-29 → response trajectory covers 09-28..09-29 AND gap rows 09-23..09-27 exist.

4. **No silent zero; provenance visible**
   - Current: rainfall miss → `0.0` with only a `print`.
   - Target: every backfilled date records its rainfall source (`client` | `live` | `batch` | `db` | `fallback-zero`); the service response includes the backfilled date list (and per-date source at least in debug payload); `fallback-zero` is explicitly flagged, never silent.
   - Acceptance: response contains `backfilled_dates` (or equivalent) covering exactly the gap computed in that call; a forced live-failure test shows the date still persisted with source `fallback-zero`.

5. **Both callers wired to the guarantee**
   - Current: `POST /predict` branches on system date; agent anchor logic lives in `tools._anchor_and_target`.
   - Target: `POST /predict` branches on IST today (same clock the service uses); agent forecast path needs no new logic beyond calling `predict_future_streamflow` (which now guarantees the gap) — but `_anchor_and_target` must not mask past targets by silently substituting `anchor+horizon` when the user gave an explicit in-window date; explicit in-window targets reach the service unchanged.
   - Acceptance: test posts a past explicit `target_date` through the agent helper and asserts the service receives that exact date (no fallback substitution) whenever it lies within the 30-day window; test posts past vs future dates to `/predict` routing logic and asserts IST-based branch selection.

## Boundaries

**In scope:**
- Shared backfill helper in `prediction_service.py` + rewiring of `run_prediction_for_station` and `predict_future_streamflow` through it
- Per-date live rainfall resolution + chained feature/predict/persist loop for the gap
- Past-target answer-from-persisted-rows behavior (no empty success)
- IST-today clock unification for the service + `/predict` branch (reuse `chat_agent.clock.today_ist` with safe fallback to system date when chat package unavailable)
- Agent `_anchor_and_target` explicit-target passthrough fix (if needed to meet R5)
- Unit/integration tests proving R1–R5; `STATE.md` update; new `LEARNINGS.md` (append-only, prior files untouched)

**Out of scope:**
- Model retraining, threshold changes, or feature-set changes — same LSTM+XGB, same 15-row window
- Re-downloading baseflow from CDS/GloFAS or changing the anchor value itself — anchor stays the CDS date
- Re-enabling the Render cron auto-sync or changing the push-model (laptop push stays) — this phase only guarantees on-demand prediction-time backfill
- Switching Open-Meteo forecast endpoint to the archive API — still forecast endpoint per-date + documented fallbacks
- New DB tables/migrations — reuse `gauge_state`, `station_rainfall_history`, existing `source` column when present
- Frontend changes — no dashboard/chat UI work

## Constraints

- Must run identically on an Indian laptop (local bootstrap via Render URL) and on Render prod: IST wall-clock without tz-database dependency (reuse `chat_agent/clock.py` pattern), graceful fallback when that module is not importable.
- Open-Meteo rate discipline: per-date live calls multiply HTTP volume; keep single-station prediction sequential and rely on existing sweep caps (`SWEEP_SYNC_CAP`) for batch paths — no new unbounded fan-out.
- No schema rewrite: additive-only persistence; `INSERT OR IGNORE/REPLACE` semantics preserved; existing `source='forecast'` provenance for future rows preserved.
- Backward compatibility: response shapes gain additive fields only (`backfilled_dates`, rainfall source info); existing keys unchanged; full existing backend suite must stay green.

## Acceptance Criteria

- [ ] Anchor 09-22 → today 09-27 → target 09-29 via EITHER service function persists gap rows 09-23..09-27 before 09-28/29 rows
- [ ] Per-date live rainfall attempt occurs once per gap date (mock-counted), `build_feature_window` once per gap date, chained state verified (N+1 input == N output)
- [ ] Target 09-25 (past) returns the 09-25 prediction with no empty-trajectory success, and gap rows 09-23..09-27 exist
- [ ] Response carries `backfilled_dates` for the gap computed in that call; forced live-failure persists the date flagged `fallback-zero`
- [ ] Explicit in-window past `target_date` reaches the model unchanged from agent tools; `/predict` past/future branch follows IST today
- [ ] Full existing backend suite green (no regressions), new tests green
- [ ] `STATE.md` updated; phase `LEARNINGS.md` written without modifying any prior phase's `LEARNINGS.md`

## Edge Coverage

**Coverage:** 5/6 applicable edges resolved · 0 unresolved (1 dismissed with reason)

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| Empty gap (anchor == today) | R1 | ✅ covered | AC: no-op backfill, `backfilled_dates == []`, target computed normally |
| Target == today | R3 | ✅ covered | AC: backfill anchor→today, answer today from persisted row |
| Live rainfall failure for every gap date | R2,R4 | ✅ covered | AC: all gap dates persist with source `fallback-zero`, flagged in response |
| `client_rainfall` covers only some gap dates | R2 | ✅ covered | AC: supplied dates use `client`, remainder use live/fallback per date |
| Anchor missing (station has zero rows) | R1 | ⛔ dismissed | Pre-existing bootstrap path (`today-60d` seed) unchanged; out of scope per Boundaries — no new behavior minted here |
| Future target far beyond 30-day agent window | R5 | 🧪 backstop | Held-out test: agent caps/fallbacks unchanged; service still backfills gap before applying existing window rule |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT fabricate observed streamflow as ground truth — backfilled rows stay model predictions, never presented as CDS observations | R1 | resolved | verification: judgment — verifier reads response/DB labels; no new "observed" flag introduced |
| MUST NOT silently zero-fill rainfall without recording `fallback-zero` provenance | R4 | resolved | verification: test — forced-failure test asserts flagged source (negative: unflagged zero fails) |
| MUST NOT rewrite history rows that already exist with a different value unless through the existing REPLACE forecast semantics | R1 | resolved | verification: test — pre-seeded gap row keeps its value when backfill revisits it |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓ | Gap + per-date features + both callers, all measurable |
| Boundary Clarity   | 0.88  | 0.70 | ✓ | Explicit in/out lists; no retrain/scheduler/schema/UI |
| Constraint Clarity | 0.85  | 0.65 | ✓ | IST portability, rate caps, additive-only responses |
| Acceptance Criteria| 0.88  | 0.70 | ✓ | 7 pass/fail checkboxes with exact dates |
| **Ambiguity**      | 0.12  | ≤0.20| ✓ | 1 − (0.35×0.90 + 0.25×0.88 + 0.20×0.85 + 0.20×0.88) = 0.119 |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 0 | Scout | What exists today on each prediction path? | Mapped: service×2 + `/predict` + agent tools; batch-rainfall + silent-zero + `date.today()` gaps confirmed |
| 1 | Researcher | What counts as anchor? | CDS download date (22 Sept); latest observed row — user answer |
| 1 | Researcher | What is current date? | Portable "current time whichever day it runs" → IST — user answer |
| 1 | Simplifier | Which rainfall source per backfilled date? | Always attempt live per date — user answer |
| 1 | Seed Closer | Past target: through today or only to target? | Backfill anchor→today first, then extend/answer — user answer |

---

*Phase: 07-prediction-backfill-guarantee*
*Spec created: 2026-09-27*
*Next step: PLAN.md — implementation decisions (helper shape, clock wiring, test doubles)*
