# Phase 06-chat-reliability — PLAN.md

## Diagnosis (reproduced 2026-09-27, evidence above)
- D1 Guard: `FROM latest_flow lf` — qualifier `lf` resolves via `table_of_alias`
  to `LATEST_FLOW`, which is a CTE name, but the column check only skips
  qualifiers directly in `known_aliases`. Fix: skip when the *resolved* name
  is a known CTE/derived alias (`sql_guard.py` column loop).
- D2 Graphs: `agent.py:459` `_collect` returns early on `"error" in out`, but
  `execute_sql` always includes `"error"` (empty on success) → run_sql charts
  never built. Fix: skip only when `out.get("error")` is truthy. Verified
  `charts_from_rows` yields 5 cards from the reported query once reached.
- D3 Scroll: `ChatSidebar.tsx` `bottomRef.scrollIntoView({behavior:"smooth"})`
  on every msgs/loading change scrolls the whole document. Fix: scroll the
  messages container (`scrollTop = scrollHeight`) only when near bottom.
- D4 Date: prompt uses server IST only. Fix: `client_today` (YYYY-MM-DD) on
  `ChatRequest` + job submit/poll; agent prefers validated client date for
  prompt + staleness; frontend sends local date; invalid/missing → server date.
- D5 Names: template chart lines print bare IDs; summarizer chart descriptors
  lack names. Fix both + prompt rule "always pair station id with station_name".
- D6 Schema: no code change needed beyond D1; add both reported query shapes as
  guard regression tests (one must pass, CTE aliases in nested scopes must pass).

## Tasks (each: implement → targeted test → run suite slice)
1. `sql_guard.py`: CTE-alias-of-alias resolution; add reported queries to
   `test_sql_guard.py` (CTE-allow + nested-alias-allow); full guard battery green.
2. `agent.py` `_collect` error-truthiness fix; add test: run_sql success dict
   with `"error": ""` yields charts; run full suite.
3. `ChatSidebar.tsx`: container-local near-bottom autoscroll; tsc + build.
4. `schemas.py`/`agent.py`/`router.py`/`jobs.py` + frontend: `client_today`
   end-to-end; test with fixed client date ≠ server date; staleness uses it.
5. Names: template lines `Station {id} ({name})`; descriptors include name;
   prompt rule; test asserts name present.
6. Full verification: backend suite, tsc, vite build, live TestClient run of the
   reported top-5 flow (charts == 5, reply has names + staleness).

## No-code-without-plan gate
- This PLAN is the gate. Every fix above maps to SPEC § Acceptance criteria.
