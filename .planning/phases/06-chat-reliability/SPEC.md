# Phase 06-chat-reliability — SPEC.md

## Goal
Make the flood chat assistant foolproof on the exact failure reported 2026-09-27:
a "top 5 stations by streamflow" query produced a guard false-positive on valid
SQL, no graphs, page scroll-jank, stale-date reasoning, and bare IDs without names.

## Scope (bug-fix batch, feat/chat-sql branch; NO main merge in this phase)
1. **Guard CTE-alias false positive**: `FROM latest_flow lf` + `lf.col` must pass
   (alias-of-CTE resolution). No relaxation of real rules (writes, `*`, unknown
   tables/columns, LIMIT cap all stay denied).
2. **Missing graphs**: `run_sql` results must reach chart cards (root-cause + fix).
3. **Scroll-jank**: thinking/tool streaming must not scroll the whole page; scroll
   only the messages pane, and only when already near the bottom.
4. **User-local date**: backend must accept `client_today` (frontend local date)
   and prefer it over server date in prompt + staleness math; validated, fallback safe.
5. **Names with IDs**: every station ID rendered/mentioned must be paired with its
   `station_name` (template lines, chart descriptors for the summarizer, prompt rule).
6. **Schema grounding**: model keeps full schema every turn (already true); add the
   two reported query shapes as guard regression tests; no prompt bloat.

## Non-goals
- No new tools, no model changes, no Render/Vercel config, no main merge.
- No framework migration (hand-rolled loop stays per prior decision).

## Acceptance criteria
- The exact CTE query from the report validates `ok=True`; full adversarial
  battery still denies everything it denied before.
- The exact derived-table query returns rows AND yields 5 chart cards via `_collect`.
- 5 rapid thinking/tool events move only the messages pane (code inspection +
  tsc/build; scroll container queried, no `scrollIntoView` on page).
- `client_today` honored end-to-end (unit: prompt + staleness use it; invalid →
  server date); suite has a test with a fixed client date ≠ server date.
- Template reply lines and summarizer chart descriptors include station names.
- Full backend suite green, `tsc` clean, `vite build` succeeds.
