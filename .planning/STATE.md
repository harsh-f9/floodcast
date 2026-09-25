# STATE

- Milestone: v2-prod-harden
- Commits: a8c30b6 (Phase 01), e293b12 (ops+trust units).
- New verified, uncommitted: briefing.py (BRIEFING_PASS) + Phase 03 PLAN.
- Backend: imports to torch boundary (torch+xgb deferred, Render has them). DB 378 rows pre-reseed (fresh seed → 367). tsc EXIT 0.
- Anchor rule: base = max gauge_state (2026-07-14 now) fallback Jul14; GloFAS previous-date via baseflow_glofas; manual CSV via --from-csv. Telegram chosen for alerts (stub done, wiring deferred to Phase 05 ship).
- Next: commit briefing core, then flags/percentiles (needs residuals), scenario/intervals, delivery wiring, frontend modal upgrade.
