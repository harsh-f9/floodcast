# STATE

- Milestone: v2-prod-harden
- Anchor floor (user order): NEVER July. `MIN_ANCHOR=2026-09-22` in baseflow_glofas.
  Fresh seed → 367 stations, gauge ONLY 09-22 (verified on temp DB). Boot anchor:
  latest-published via CDS lookback, else committed floor file (verified `anchored-floor`
  367 rows from July-only DB with CDS 400). Discharge 07-10 survives only as fallback
  when floor file missing (never on Render — file is committed).
- User deploying Render manually with env vars set. Code pushed; auto-deploy picks it up.

## Phase 06-chat-reliability [DONE 2026-09-27, feat/chat-sql, no main merge]
Fixed user-reported top-5 failure: guard CTE-alias allow, _collect error-truthiness
(graphs restored), container-local autoscroll, client_today end-to-end, names paired
with IDs, reported queries as regression tests. 158/158 backend green, tsc+build clean,
live top-5 verified (5 charts, staleness stated). See phases/06-chat-reliability/.

## Phase 07-prediction-backfill-guarantee [DONE 2026-09-27]
Every prediction call (agent tools + user POST /predict) for a target date first
computes anchor→today sequentially with per-date live rainfall + window + chained
model state, then answers/extends to target. Decisions: anchor = CDS download date
(latest persisted row); today = portable IST (chat clock → +5:30 → system); rainfall
= live attempt per date with 429 breaker + batch/db/fallback-zero provenance;
past targets backfill through today then answer from persisted rows. Shared helpers
`ensure_anchor_to_today/_step_single_date/_resolve_rainfall_for_date` in
`prediction_service.py`; `/predict` branches on IST; agent tools unchanged (passthrough
verified). 169/169 backend green (158 existing + 11 new in
`backend/chat_agent/tests/test_backfill_guarantee.py`). See
phases/07-prediction-backfill-guarantee/{SPEC,PLAN,VERIFICATION,LEARNINGS}.md.
Prior phases' LEARNINGS.md files untouched.
