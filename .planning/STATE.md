# STATE

- Milestone: v2-prod-harden
- Commits through b9008fc (briefing UI) + this: inference hardening + delivery wiring.
- Inference verified live (torch CPU): validate 3/3, smoke 09-23 → 0.0 clamped (anchor discontinuity 825→0.19 documented, not hidden), anchor off-by-one fixed, test rows cleaned (max 09-22).
- Delivery live: stamped /predict + mounted Telegram webhook (log-only without env).
- Still held: residual percentiles → intervals/baseline UI (needs colab), dummy-API label + ProjectDetail live page (product pick), dashboard stamp footer (trivial), Render re-anchor POST on deploy.
