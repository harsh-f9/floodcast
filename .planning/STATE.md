# STATE

- Milestone: v2-prod-harden
- Current: Phase 01-freeze-contract FIXES VERIFIED, awaiting user commit approval. No commits made.
- Done 2026-09-25: SCHEMA.md, validation.py (+EXCLUDED_11, inf guard), migrations/ (idempotent runner + WAL/FK + wired to startup), seed validates before rename + filters 378→367 preserving stable IDs, admin sync 400s, cro gate → confirm, Station type fix (tsc 4→0).
- Verify: BACKEND_COMPILE_OK, validation PASS, gauges 378/0bad PASS, migrations [(1,)] PASS, tsc EXIT 0 PASS. Full-stack inference still blocked: system python lacks fastapi/pandas/torch (venvs broken); DB present 378 stations (will become 367 on fresh seed); admin open (Phase 05 Telegram planned); anchors diverged (anchor-aware fix scoped in Phase 03).
- User inputs locked: Telegram, anchor-aware dates (Copernicus manual), remove cro DONE, filter 367 DONE, no commits until exhaustive verify (this STATE + EXHAUSTIVE_VERIFY.md).
- Next (needs user go): commit Phase 01? Then Phase 02-trust-layer PLAN.
