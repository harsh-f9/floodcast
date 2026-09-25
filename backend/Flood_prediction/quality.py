"""Quality flags (migratable, Phase 02 part).

Pure rules + thin SQLite writer. No imports from database/prediction at top
(lazy inside writer). Delete file to remove feature.

Flags:
- station_silent_48h: max gauge_state date gap >= 2d vs reference date.
- value_out_of_range: flow < 0 or flow > rp_20 (rp_200 proxy; repo has only rp_2/5/15/20).
- spike_vs_neighbors: |q-med|/(med+eps) > 3 with n>=3 and local rain low.
"""


def silent_gap_days(last_date_iso: str | None, ref_date_iso: str) -> int | None:
    if not last_date_iso:
        return None
    try:
        from datetime import date

        return (date.fromisoformat(ref_date_iso) - date.fromisoformat(last_date_iso)).days
    except ValueError:
        return None


def is_silent(last_date_iso: str | None, ref_date_iso: str, threshold_days: int = 2) -> bool:
    gap = silent_gap_days(last_date_iso, ref_date_iso)
    return gap is not None and gap >= threshold_days


def is_out_of_range(flow: float, rp_20: float | None) -> bool:
    try:
        f = float(flow)
    except (TypeError, ValueError):
        return True
    if f < 0:
        return True
    if rp_20 is not None:
        try:
            if f > float(rp_20):
                return True
        except (TypeError, ValueError):
            pass
    return False


def is_spike(flow: float, neighbor_flows: list[float], rain_mm: float = 0.0,
             min_n: int = 3, ratio: float = 3.0) -> bool:
    xs = [float(x) for x in neighbor_flows if x is not None]
    if len(xs) < min_n:
        return False
    xs.sort()
    med = xs[len(xs) // 2]
    try:
        f = float(flow)
    except (TypeError, ValueError):
        return False
    if abs(f - med) / (abs(med) + 1e-6) <= ratio:
        return False
    return rain_mm < 20.0  # high local rain explains spike; low rain => suspect


def write_flags(flags: list[tuple[int, str, str, str]]) -> int:
    """Write [(station_id, date, flag, detail_json)] via database module (lazy)."""
    if not flags:
        return 0
    try:
        from Flood_prediction import database as db
    except ImportError:
        import database as db
    db.executemany(
        "INSERT OR REPLACE INTO quality_flags (station_id, date, flag, detail) VALUES (?,?,?,?)",
        [list(f) for f in flags],
    )
    return len(flags)
