# Onboarding Summary

## Project State
- PROJECT.md: present
- ROADMAP.md: present
- STATE.md: present
- Codebase map: via subagents 2026-09-25 (backend + frontend), not yet persisted to `.planning/codebase/`

## Codebase Context
- Brownfield: yes
- Git root: `crowebsite/` (has `.git`)
- Research outside git root: `../colab/` + `../colab/PIPELINE_DATA_PROCESSING.md` + `../Flood_Resume_Context.md`
- Canonical model: `backend/Flood_prediction/deploy/` (3.3MB pt real). Do NOT use `C:/CRO/CRO`.
- DB: `backend/Flood_prediction/database.py` 4 tables, no migrations yet
- API split: real `/predict` (hybrid) vs dummy `/api/predict` (randomized) — keep separated
- Frontend: `src/pages/FloodDashboard.tsx` 1661 lines, hardcoded `2026-07-14/21`, `prompt()=="cro"`

## Docs Context
- Pipeline doc: `colab/PIPELINE_DATA_PROCESSING.md` §§0-8 (367×8757, 52-55 cols, _yj rule, 11-gauge gap)
- Resume context: `Flood_Resume_Context.md` (honesty tiers SHIPPED/BUILT/PROTOTYPE/PLANNED)

## Recommended Next
- Phase 01-freeze-contract: SPEC → PLAN → VERIFICATION → code
