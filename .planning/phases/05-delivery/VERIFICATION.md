# Phase 05-delivery — VERIFICATION.md (partial)

Date: 2026-09-25. Torch CPU 2.14 + xgboost live.

## Inference gates
- `Flood_prediction.validate`: 3/3 samples diff ≤0.0008 (limit 0.5). PASS.
- Smoke station 0 → 2026-09-23 from 09-22 GloFAS anchor (0.19): raw model delta
  overshoots on the July-chain→GloFAS discontinuity → clamped to 0.0, stored 0.0
  (was -1.06 before clamp). Honest result: model cannot bridge the 825→0.19 anchor
  jump; flagged for intervals work, not hidden. Test rows cleaned (max back to 09-22).
- Anchor fix verified: response anchor 0.19 (was 825.18), delta -0.19.

## Wiring (TestClient, dev DB)
- `POST /predict {0, 2026-09-23}` → 200, stamp present
  (`hybrid-lstm-xgb-32d-256h-835c1591` / `2026-09-23` / `63b7b4f490ac`), pred 0.0 anchor 0.19.
- `POST /api/admin/alert-webhook` EXTREME without env → 200 log-only stub. PASS.
- `import main` OK, 13→14 routes (alerts added).
