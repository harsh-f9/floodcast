# OPS Runbook — laptop-first, Render as fallback mirror

> Primary host is the **laptop** (`start_local.bat` → `http://localhost:8000`).
> DB persists, no cold starts, scheduler works. Render section below is fallback only.
> Interview-day procedure: see `INTERVIEW_GUIDE.md`.

## Render (fallback mirror)

## Why the push model exists
Calling Open-Meteo for all ~367 stations at once returns 429s. Render therefore
**never** calls Open-Meteo in cron/scheduler/bootstrap. The laptop fetches in small
chunks and pushes via admin sync endpoints. Do not "simplify" this without re-measuring.

## Rate-limit discipline (numbers)
- Rain: 50 stations/request, 3s gap, 5 retries exp backoff (`local_bootstrap.py`).
- Baseflow: 1 CDS request/day-range for whole bbox (`baseflow_glofas.py`).
- Statewide predict: chunks of 8 (`FloodDashboard.tsx`, keeps Render free tier alive).
- Render cold start sleeps: laptop scripts retry `/stations` 3× (wake 20s apart).

## Env vars
| Var | Where | Purpose |
|---|---|---|
| `BACKEND_URL` | laptop shell | Target for push scripts (default Render prod) |
| `CDS_API_KEY` | `backend/.env` (gitignored) + Render dashboard | GloFAS download via `baseflow_glofas.py` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Render dashboard | Alert webhook (Phase 05 wiring) |
| `FLOOD_CRON_DRY_RUN=1` | Render dashboard (optional) | Scheduler logs only, no Open-Meteo |
| `DATABASE_PATH` | Render only if persistent disk | SQLite path; free-tier ephemeral disk wipes on redeploy |

## Scripts (all standalone, delete-safe)
- `local_bootstrap.py` — rain window push. Default: anchor = yesterday IST, lookback 60d.
  `--dry-run --limit 2` = safe connectivity test (no writes). `--smoke-id 0` = read-only check.
- `backend/Flood_prediction/baseflow_glofas.py` — GloFAS anchor for previous date,
  auto-steps back (`--lookback 7`) over unpublished dates (~2d latency). Emits audit CSV
  + `sync_*.json` under `deploy/baseflow/`. `--from-csv` converts manual downloads.
- `upload_actuals.py` — pushes anchors: long CSV (`station_id,date,raw_streamflow`) or
  baseflow sync JSON (auto-detected). `INSERT OR REPLACE` (overwrites forecasts — intended).

## Cold start (automatic, `backend/main.py:startup`)
reset-check → init_tables → run_migrations (001+002) → seed if empty (367, stable IDs,
anchor = discharge values) → bootstrap (server-side DISABLED by design) → scheduler.
Fresh DB has statics + anchors, **no rain**. Nothing predicts until laptop pushes.

## Full re-anchor (fresh deploy / disk wipe)
1. Wait for spin-up: `python local_bootstrap.py --limit 2 --dry-run` until `[OK]`.
2. Rain: `python local_bootstrap.py` (full 367; ~8 chunks, several minutes, 429-safe).
3. Anchor: `PYTHONPATH=backend python -m Flood_prediction.baseflow_glofas`
   then `python upload_actuals.py backend/Flood_prediction/deploy/baseflow/sync_YYYY-MM-DD.json`.
4. Smoke (read-only): `python local_bootstrap.py --limit 2 --dry-run --smoke-id 0`.
5. Advance chain: run district/statewide Master Predict from dashboard (each `/predict`
   writes `gauge_state` forward; responses carry `model_version`/`db_date`/`generation_id`
   once Phase 05 wiring lands — for now check trajectory dates).

## Monitoring (sqlite, read-only)
- Staleness: `SELECT MAX(date) FROM gauge_state;` vs today (≥2d gap = `station_silent_48h`).
- Flags: `SELECT flag, COUNT(*) FROM quality_flags GROUP BY flag;` (needs 002 migration).
- Counts: `SELECT COUNT(*) FROM station_static;` (367 post-reseed) and per-date gauge rows.

## Rollback
Delete `flood_prediction.db` (+ `-shm`/`-wal`) beside `database.py`, restart backend,
re-run re-anchor above. History is re-derivable from committed sync JSONs + Open-Meteo
(rain) — never hand-edit rows.
