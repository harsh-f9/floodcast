# STATE

- Milestone: v2-prod-harden
- Phase 01: COMMITTED (a8c30b6).
- New verified, ready to commit: baseflow_glofas.py (+deploy/baseflow audit+sync example), 002_trust_layer.py, alerts.py (Telegram stub, router live), scheduler DRY_RUN, version_stamp.py (model_version hybrid-lstm-xgb-32d-256h-835c1591, db_date 2026-07-14).
- Backend verify: seed_db import OK, stations 378 (pre-reseed), main imports to torch boundary (pandas/fastapi/httpx/apscheduler/requests/sklearn/joblib installed; torch+xgboost deferred as heavy, Render has them).
- tsc: EXIT 0 (Station fix).
- Next: commit ops+trust units, then Phase 02 flags/percentiles (needs residuals), Phase 03 briefing generator, Phase 04 scenario/intervals, Phase 05 wire version+alerts+unify APIs.
- Anchor rule: base = max gauge_state (now 2026-07-14) fallback Jul14; previous-date GloFAS via baseflow_glofas; manual CSV via --from-csv. No blind today-switch (Copernicus manual).
