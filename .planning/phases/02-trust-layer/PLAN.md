# Phase 02-trust-layer — PLAN.md (partial, 2026-09-25)

## Done (verified)
- `migrations/002_trust_layer.py`: additive ingested_at/source + quality_flags, PRAGMA-guarded, idempotent. Verified on temp DB: versions [(1,),(2,)], rerun stable.

## Pending (needs pandas/env or residuals)
- Wire source values (open-meteo|client-override|admin-sync|bootstrap|glofas-baseflow) through insert_rainfall/gauge_state (defaults already backfill).
- Flag compute (silent_48h, out_of_range rp_20 proxy, spike_vs_neighbors district median) off hot path — in sync/scheduler + /station read.
- Fill station_flow_percentiles from held-out residuals per regime (no npz in repo; reconstruct offline in colab).
- UI: staleness badge, confidence line, collapse debug_features, proxy assets panel.

## Rewrite check
Patch so far (one migration file). database.py untouched. If >2 patches touch database.py, split to db/migrations/ per rule.
