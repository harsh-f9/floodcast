# STATE

- Milestone: v2-prod-harden
- Anchor floor (user order): NEVER July. `MIN_ANCHOR=2026-09-22` in baseflow_glofas.
  Fresh seed → 367 stations, gauge ONLY 09-22 (verified on temp DB). Boot anchor:
  latest-published via CDS lookback, else committed floor file (verified `anchored-floor`
  367 rows from July-only DB with CDS 400). Discharge 07-10 survives only as fallback
  when floor file missing (never on Render — file is committed).
- User deploying Render manually with env vars set. Code pushed; auto-deploy picks it up.
