# Migrations — usage
```python
from Flood_prediction.migrations.runner import run_migrations
run_migrations()  # call after init_tables() in startup
```
- Add `NNN_name.py` with `def migrate(conn): ...` using `PRAGMA table_info` guards (SQLite has no ADD COLUMN IF NOT EXISTS).
- `001_baseline.py` documents 4-table baseline, no-op.
- Phase 02 adds `002_trust_layer.py` (ingested_at/source + quality_flags).
