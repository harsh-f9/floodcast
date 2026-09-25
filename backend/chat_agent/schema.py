"""Governed schema catalog for the chat agent's SQL surface.

Single source of truth: the LLM prompt context, the table allowlist, and the
per-table column allowlist are all derived from CATALOG below. Raw DDL names
columns but not meaning, so each entry carries semantic notes (what the table
is, what key thresholds mean, what NOT to assume).

Not in the database (do not invent): district names live in the frontend
enriched-gauge JSON, not in SQLite. District scoping uses the
district_stations tool; SQL is for cross-station analytics.
"""

CATALOG = {
    "station_static": {
        "description": (
            "One row per flood gauge station (367 stations). "
            "station_name holds the gauge id like 'hybas_4120789590'. "
            "rp_2/rp_5/rp_15/rp_20 are return-period flow thresholds in m3/s: "
            "rp_2 = WATCH level, rp_5 = WARNING level, "
            "rp_15 = DANGER level, rp_20 = EXTREME level."
        ),
        "columns": {
            "station_id": "integer primary key, stable gauge number",
            "station_name": "gauge id text, e.g. hybas_4120789590",
            "latitude": "real, degrees north",
            "longitude": "real, degrees east",
            "UP_AREA": "real, upstream catchment area",
            "DIST_SINK": "real, network distance to sink in km",
            "slp_dg": "real, slope",
            "slp_dg_uav": "real",
            "for_pc": "real, forest percent",
            "urb_pc": "real, urban percent",
            "attenuation_factor": "real",
            "flow_velocity_km_per_day": "real",
            "upstream_lag1_days": "real",
            "upstream_lag2_days": "real",
            "rp_2": "real m3/s, WATCH threshold",
            "rp_5": "real m3/s, WARNING threshold",
            "rp_15": "real m3/s, DANGER threshold",
            "rp_20": "real m3/s, EXTREME threshold",
            "max_30d_rain": "real mm",
        },
    },
    "gauge_state": {
        "description": (
            "Daily streamflow per station (latest model predictions / anchored actuals). "
            "date is TEXT in ISO format YYYY-MM-DD. raw_streamflow is in m3/s. "
            "Join to station_static on station_id for thresholds."
        ),
        "columns": {
            "station_id": "integer, joins station_static.station_id",
            "date": "text ISO date YYYY-MM-DD",
            "raw_streamflow": "real m3/s",
            "ingested_at": "text, bookkeeping",
            "source": "text, bookkeeping",
        },
    },
    "station_rainfall_history": {
        "description": "Daily rainfall per station in mm. date is TEXT YYYY-MM-DD.",
        "columns": {
            "station_id": "integer, joins station_static.station_id",
            "date": "text ISO date YYYY-MM-DD",
            "rainfall_mm": "real mm per day",
            "ingested_at": "text, bookkeeping",
            "source": "text, bookkeeping",
        },
    },
    "station_flow_percentiles": {
        "description": "Per-station flow percentile reference values (JSON array text).",
        "columns": {
            "station_id": "integer, joins station_static.station_id",
            "percentile_values": "text JSON array",
        },
    },
}

ALLOWED_TABLES = frozenset(CATALOG.keys())
ALLOWED_COLUMNS = {t: frozenset(meta["columns"].keys()) for t, meta in CATALOG.items()}

MAX_SQL_ROWS = 100


def schema_prompt() -> str:
    lines = ["Queryable SQLite tables (use ONLY these tables and columns):"]
    for table, meta in CATALOG.items():
        lines.append(f"- {table}: {meta['description']}")
        lines.append("  columns: " + ", ".join(sorted(meta["columns"].keys())))
    lines.append(
        "Join stations to flows/rain with station_id. "
        "District names are NOT in the database — never filter on a district column."
    )
    return "\n".join(lines)
