# Phase 05-delivery — PLAN.md (partial, 2026-09-25)

## Done (verified live via TestClient, torch CPU)
- Version stamp on every `/predict`: `model_version` (sha of model_config + arch tag),
  `db_date` (max gauge_state at generation), `generation_id` (uuid12). Lazy import with
  fallback; stamp skipped (logged) rather than failing prediction if helper missing.
- Alerts router mounted (`/api/admin/alert-webhook`, Telegram). Without env: 200 log-only
  stub. Wiring is one include block; `alerts.py` stays deletable.
- Inference hardening found by live smoke (station 0, 09-22 anchor 0.19):
  `clamp_flow()` (max(0), NaN-safe) at all 3 predictor-consumption sites — frozen
  `predictor.py` untouched. Anchor off-by-one fixed (`before_date` excludes target, so
  index 0 is the anchor; was index 1 → reported 07-14 value 825.18, also poisoned debug window).

## Pending
- Dummy vs real API copy: mark `/api/predict` demo-only in ProjectDetail UI (one label).
- One ProjectDetail flood page wired live (needs product decision on which project).
- Residual percentiles (needs offline colab reconstruction) → intervals + persistence baseline (Phase 04).
- Dashboard footer showing stamp (reads `/predict` response fields; trivial follow-up).
