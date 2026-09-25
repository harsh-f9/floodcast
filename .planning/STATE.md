# STATE

- Milestone: v2-prod-harden
- Commits: …7fc9497 (live baseflow), 27f4c42 (secrets), + ops-hardening (this).
- Push pipeline productionized: local_bootstrap anchor-aware (yesterday IST, was hardcoded 2026-07-16) + --dry-run/--limit/--smoke-id + cold-start retry (verified live vs prod: wake on 2nd try, 2 stations, 122 records, 0 writes) + client pre-validation.
- upload_actuals accepts sync JSON (367/0 skipped verified) + long CSV (unchanged path).
- OPS_RUNBOOK.md: 429 rationale, discipline numbers, env table, cold start, 5-step re-anchor, monitoring SQL, rollback.
- Prod notes: Render DB still 378 pre-reseed; local dev anchored 2026-09-22. No prod writes this window.
- Still held: torch smoke, frontend modal/scenario UI, residual percentiles, delivery wiring.
