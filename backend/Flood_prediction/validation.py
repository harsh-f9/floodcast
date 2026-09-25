"""Lightweight ingest validation (Phase 01). ~30 lines asserts, no pandera/GE on Render."""
from datetime import date

UP_LAT = (23.5, 31.0)
UP_LON = (77.0, 85.0)

REQUIRED_STATIC = ["gauge_id", "latitude", "longitude", "rp_2", "rp_5", "rp_15", "rp_20"]

# EDA-5: 11 gauges in v6/rainfall-378 but not in 367-station model panel. Serve 367.
EXCLUDED_11 = {
    "hybas_4121486100",
    "hybas_4120878420",
    "hybas_4120888940",
    "hybas_4121472500",
    "hybas_4120878430",
    "hybas_4120888130",
    "hybas_4120881440",
    "hybas_4120854010",
    "hybas_4121445720",
    "hybas_4120889880",
    "hybas_4120855950",
}


def validate_station_row(row: dict):
    for c in REQUIRED_STATIC:
        if c not in row or row[c] is None or (isinstance(row[c], float) and row[c] != row[c]):
            raise ValueError(f"missing required col: {c} in {row.get('gauge_id')}")
    lat, lon = float(row["latitude"]), float(row["longitude"])
    if not (UP_LAT[0] <= lat <= UP_LAT[1] and UP_LON[0] <= lon <= UP_LON[1]):
        raise ValueError(f"out-of-bbox {row['gauge_id']}: {lat},{lon}")
    rp2, rp5, rp15, rp20 = (float(row[k]) for k in ["rp_2", "rp_5", "rp_15", "rp_20"])
    if not (rp20 > rp15 > rp5 > rp2 > 0):
        raise ValueError(f"bad rp ordering {row['gauge_id']}: {rp2},{rp5},{rp15},{rp20}")


def validate_date(s: str) -> str:
    date.fromisoformat(s)  # raises ValueError
    return s


def validate_rainfall(v: float) -> float:
    v = float(v)
    if not (0.0 <= v <= 500.0):
        raise ValueError(f"rainfall out of range: {v}")
    return v


def validate_streamflow(v: float) -> float:
    import math

    v = float(v)
    if not (math.isfinite(v) and v >= 0.0):
        raise ValueError(f"streamflow invalid: {v}")
    return v
