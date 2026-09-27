# Phase 07 learnings (GSD extract — 2026-09-27)

1. **Anchor is max-row, not max-observed**: `get_gauge_state(limit=1)` returns the
   latest row of any source, so a stored forecast becomes the anchor. Seeding a
   test row mid-gap moves the anchor — two test failures came from this, not from
   implementation bugs. Rule: derive test anchors from the fake, never assume them.
2. **fetch_rainfall_mm erases failure identity**: it swallows exceptions into 0.0,
   so genuine zero and failed fetch are indistinguishable downstream. Fix pattern:
   add a `_or_raise` twin for the resolver and keep the swallowing wrapper for
   backward compat.
3. **Always-live needs a circuit breaker**: per-date singles multiply HTTP volume
   (sweep 40 stations x 5 days = 200 calls). A 429 flips `live_disabled` for the
   rest of the call plus one lazy bulk fetch — honors "attempt live per date"
   without risking an IP ban. Batch pre-fetch upfront would have doubled every call.
4. **Debug-rebuild counts as a window call**: the final `build_feature_window` for
   `debug_features` fires even when the gap loop is empty — mock-count assertions
   must expect `computed_dates + [target]`, not `computed_dates`.
5. **cp1252 breaks naive source reads**: backend files contain emoji; any
   `open()` without `encoding="utf-8"` (or missing `PYTHONUTF8=1`) crashes on
   Windows. Applies to ad-hoc verification scripts, not just the app.
6. **INSERT OR IGNORE splits memory from disk**: stored rainfall wins on disk
   while the fresh live value drives the in-memory chain (inherited semantics,
   kept deliberately). Any future "live refreshes history" change must be an
   explicit decision, not an accident.
