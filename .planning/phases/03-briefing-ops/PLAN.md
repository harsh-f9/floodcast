# Phase 03-briefing-ops — PLAN.md (partial, 2026-09-25)

## Done (verified, committed or ready)
- Baseflow automation: `baseflow_glofas.py` + `deploy/baseflow/` (audit CSV + sync JSON) — VERIFICATION-baseflow.md PASS.
- Scheduler DRY_RUN flag + push-model docstring — COMPILE_OK.
- Briefing core: `briefing.py` pure `summarize_district()` — BRIEFING_PASS (synthetic 2-gauge: peak hybas_B EXTREME, counts, rainiest window, action line).

## Pending
- Frontend: upgrade report modal with briefing paragraph + copy/download; anchor-aware base (max gauge_state fallback 2026-07-14) instead of hardcoded 2026-07-14/21; honest anchor-limited label.
- Backend wiring (Phase 05 ship): expose briefing via endpoint or compute client-side from existing master-predict data (preferred: no new API, reuse trajectory+rain_window+thresholds).

## Rewrite check
Additive single file. No edits to prediction_service/database/main. Frontend modal edit pending (isolated prop).
