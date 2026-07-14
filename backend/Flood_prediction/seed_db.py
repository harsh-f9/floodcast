"""
One-time database seeder for the Flood Prediction system.
Reads gauges_info.csv and discharge_24March.csv, populates all tables.

Run once:  python -m Flood_prediction.seed_db
"""

import os
import sys
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_tables, execute, executemany, get_station_count, query_one
)

DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")
GAUGES_CSV = os.path.join(DEPLOY_DIR, "gauges_info.csv")
DISCHARGE_CSV = os.path.join(DEPLOY_DIR, "discharge_1007.csv")
BOOTSTRAP_DATE = "2026-07-10"


def seed():
    """Seed all tables from CSV files."""
    print("🔄 Initializing database tables...")
    init_tables()

    # Check if already seeded
    if get_station_count() > 0:
        print("⚠️  Database already seeded. Skipping. Delete flood_prediction.db to re-seed.")
        return

    # ── 1. Load gauges_info.csv ────────────────────────────────────────
    print(f"📖 Reading {GAUGES_CSV}...")
    gauges = pd.read_csv(GAUGES_CSV)

    # Assign numeric station_id from row index
    gauges = gauges.reset_index(drop=True)
    gauges["station_id"] = gauges.index
    gauges = gauges.rename(columns={"gauge_id": "station_name"})

    print(f"   Found {len(gauges)} stations.")

    # ── 2. Load discharge_1007.csv ──────────────────────────────────
    print(f"📖 Reading {DISCHARGE_CSV}...")
    discharge = pd.read_csv(DISCHARGE_CSV)
    discharge = discharge.rename(columns={"Hybas_ID": "station_name"})
    discharge_map = dict(zip(discharge["station_name"], discharge["river_discharge"]))
    print(f"   Found {len(discharge_map)} discharge records.")

    # ── 3. Populate station_static ─────────────────────────────────────
    print("💾 Seeding station_static...")
    station_rows = []
    for _, row in gauges.iterrows():
        station_rows.append((
            int(row["station_id"]),
            str(row["station_name"]),
            float(row["latitude"]),
            float(row["longitude"]),
            float(row.get("UP_AREA", 0.0)),
            float(row.get("DIST_SINK", 0.0)),
            float(row.get("slp_dg", 0.0)),
            float(row.get("slp_dg_uav", 0.0)),
            float(row.get("for_pc", 0.0)),
            float(row.get("urb_pc", 0.0)),
            float(row.get("attenuation_factor", 0.0)),
            float(row.get("flow_velocity_km_per_day", 0.0)),
            float(row.get("upstream_lag1_days", 0.0)),
            float(row.get("upstream_lag2_days", 0.0)),
            float(row.get("rp_2", 0.0)),
            float(row.get("rp_5", 0.0)),
            float(row.get("rp_15", 0.0)),
            float(row.get("rp_20", 0.0)),
            0.0,  # max_30d_rain — will be computed during bootstrap
        ))

    executemany(
        "INSERT INTO station_static "
        "(station_id, station_name, latitude, longitude, UP_AREA, DIST_SINK, "
        "slp_dg, slp_dg_uav, for_pc, urb_pc, attenuation_factor, "
        "flow_velocity_km_per_day, upstream_lag1_days, upstream_lag2_days, "
        "rp_2, rp_5, rp_15, rp_20, max_30d_rain) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        station_rows
    )
    print(f"   ✅ Inserted {len(station_rows)} stations into station_static.")

    # ── 4. Seed gauge_state with March 24 observed streamflow ──────────
    print("💾 Seeding gauge_state with March 24 discharge...")
    gauge_rows = []
    matched = 0
    for _, row in gauges.iterrows():
        station_name = row["station_name"]
        discharge_val = discharge_map.get(station_name, 0.0)
        if station_name in discharge_map:
            matched += 1
        gauge_rows.append((
            int(row["station_id"]),
            BOOTSTRAP_DATE,
            float(discharge_val),
        ))

    executemany(
        "INSERT OR IGNORE INTO gauge_state (station_id, date, raw_streamflow) "
        "VALUES (?,?,?)",
        gauge_rows
    )
    print(f"   ✅ Inserted {len(gauge_rows)} gauge_state records ({matched} matched discharge values).")

    # ── 5. Seed station_flow_percentiles (empty arrays) ────────────────
    print("💾 Seeding station_flow_percentiles...")
    percentile_rows = [(int(row["station_id"]), "[]") for _, row in gauges.iterrows()]
    executemany(
        "INSERT OR IGNORE INTO station_flow_percentiles (station_id, percentile_values) "
        "VALUES (?,?)",
        percentile_rows
    )
    print(f"   ✅ Inserted {len(percentile_rows)} percentile records.")

    print("\n🎉 Database seeding complete!")
    print(f"   Stations: {get_station_count()}")


if __name__ == "__main__":
    seed()
