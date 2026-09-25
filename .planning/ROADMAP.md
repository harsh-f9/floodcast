# ROADMAP — v2-prod-harden

Milestone: production hardening, migratable, no re-run of research chain.

## Phase 01-freeze-contract [IN-PROGRESS]
Goal: freeze heterogeneous sources to versioned contract.
Outputs: `SCHEMA.md`, `migrations/` infra, validation in `seed_db.py` + admin sync.
Gates: code-review.

## Phase 02-trust-layer [PLANNED]
Additive `ingested_at,source` + `quality_flags` table, fill `station_flow_percentiles` from residuals, staleness badge + confidence line, collapse debug_features. No schema rewrite.
Gates: code-review + ui-review.

## Phase 03-briefing-ops [PLANNED]
Fix `2026-07-14/21` → today/today+7, briefing generator (~100 lines Jinja-string) with copy/download, document push-model (Render never calls Open-Meteo in cron), DRY_RUN flag.
Gates: code-review + ui-review.

## Phase 04-scenario-intervals [PLANNED]
What-if rainfall control via existing `client_rainfall_data` override, p10/p90 band from residuals, persistence baseline. No retrain.
Gates: code-review + ui-review.

## Phase 05-delivery [PLANNED]
Stamp `model_version+db_date+generation_id`, `/api/admin/alert-webhook` via env, separate real `/predict` vs dummy `/api/predict`, replace `prompt()=="cro"` with rate-limit+confirm, wire one ProjectDetail flood page live.
Gates: code-review + secure-phase + ui-review.

Each phase: SPEC.md → PLAN.md → VERIFICATION.md before code.
