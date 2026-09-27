# Phase 06 learnings (GSD extract — 2026-09-27)

1. **Envelope-shaped results vs key-presence checks**: `execute_sql` always
   carries `"error"` ("" on success). Any collector testing `"error" in out`
   silently drops all successes. Rule: assert on `ok is False` / truthy error.
2. **sqlglot alias layers**: CTE *names*, CTE *reference aliases*
   (`FROM cte lf`), and subquery aliases are three different namespaces.
   Allowlists must resolve alias→real→CTE before judging.
3. **Mock records references**: `call_args` bodies mutated later by the code
   under test (our `del body["reasoning"]`) — assert on deep copies.
4. **Tests must not depend on live DB freshness**: backfill features change
   what "stale" means; use fakes for freshness-dependent paths.
5. **Edit-tool discipline**: "identical" old/new strings with trailing-
   whitespace differences collapse newlines and merge lines. Never send
   no-op edits; always change real text and recompile + run tests after.
6. **Seed-path depth bug pattern**: path depth must be recomputed per file
   location (`seed_db.py` vs `district_map.py` vs migration); fresh-checkout
   verification (seed → migrate → test) catches what dev-DB runs hide.
7. **Free-tier model behaviors to code around**: empty 200 completions (retry),
   400-on-reasoning (process-wide disable + retry clean), slow tiers (120s
   timeout, paid rescue only on traffic errors).
