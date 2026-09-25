# STATE

- Milestone: v2-prod-harden
- Commits: a8c30b6, e293b12, 5ba13e1, quality flags, 27f4c42 (secrets gitignore).
- Baseflow LIVE 2026-09-25: CDS key in backend/.env (gitignored). `--date 2026-09-24` 400, `--date 2026-09-22` success; `--lookback` fallback (default 7) resolves any current date to latest-published (verified 24→23→22). Local dev DB anchored 367 rows 2026-09-22 (max was 2026-07-14). Prod DB untouched.
- GloFAS latency ~2 days: automation must keep fallback; UI anchor-aware base = max gauge_state (now 2026-09-22 locally).
- Still held: torch inference smoke (needs torch+xgb), frontend modal/scenario UI, residual percentiles, delivery wiring (main.py rewrite budget).
