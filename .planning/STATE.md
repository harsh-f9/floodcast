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
