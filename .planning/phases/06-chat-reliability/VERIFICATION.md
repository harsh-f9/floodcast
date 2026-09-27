# Phase 06-chat-reliability — VERIFICATION.md (2026-09-27)

## Reported incident → outcome
- CTE-alias denial (`lf.*` ×5): now validates `ok=True` (repro + regression test).
- Missing graphs: root cause `_collect` dropped every `run_sql` result
  (`"error" in out` vs always-present `""`); fixed, covered by test.
- Live re-run of "Top 5 stations by streamflow" (`client_today 2026-09-27):
  200, 1×run_sql ok, **5 charts**, reply pairs IDs with districts, states
  "gauge data from 2026-09-22 (5 days old)", severity + no-action briefing.

## Checks
- Backend suite: **158/158 OK** (incl. 2 reported-query guard regressions,
  CTE/nested-alias allows, full adversarial battery still denying).
- `tsc --noEmit`: clean. `vite build`: succeeds.
- Scroll: container-local near-bottom autoscroll only (inspection; no page-level
  `scrollIntoView` remains).
- `client_today`: prompt + staleness use it (unit with fixed date ≠ server date);
  invalid → server IST; threaded through sync/stream/jobs + resume; frontend
  sends local date on all chat POSTs.
- Names: template lines `Station 92 (hybas_…)`, summarizer descriptors carry
  names + units; prompt rule added. Live summary paired IDs with districts
  (names present in chart cards) — accepted.

## Deferred (documented, not in scope)
- Vercel-serverless long jobs (Render-only documented in jobs.py).
- Full tenant auth on jobs (queue cap + cancel + kill switch as proportionate control).
