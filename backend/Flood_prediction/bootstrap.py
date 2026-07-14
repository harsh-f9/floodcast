"""
Bootstrap script for the Flood Prediction system.
Fetches 60 days of historical rainfall for all stations from Open-Meteo,
populates station_rainfall_history, and computes max_30d_rain.

Run once after seed_db.py:  python -m Flood_prediction.bootstrap

Uses batch API calls (one call per station for the entire 60-day range)
to minimize API calls: ~367 total instead of 22,020.
"""

import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    get_all_stations, insert_rainfall, update_max_30d_rain,
    get_station_count, query_one
)
from prediction_service import fetch_rainfall_batch

BOOTSTRAP_DATE = date(2026, 7, 11)  # First prediction date
LOOKBACK_DAYS = 60


def bootstrap():
    """Fetch 60 days of rainfall for all stations and compute max_30d_rain."""
    station_count = get_station_count()
    if station_count == 0:
        print("❌ No stations found. Run seed_db.py first!")
        return

    # Check if already bootstrapped
    rain_check = query_one(
        "SELECT COUNT(*) as cnt FROM station_rainfall_history"
    )
    if rain_check and rain_check["cnt"] > 0:
        print(f"⚠️  station_rainfall_history already has {rain_check['cnt']} rows.")
        print("   Delete flood_prediction.db and re-seed to re-bootstrap.")
        return

    stations = get_all_stations()
    start_date = BOOTSTRAP_DATE - timedelta(days=LOOKBACK_DAYS)  # Jan 24, 2026
    end_date   = BOOTSTRAP_DATE - timedelta(days=1)              # Mar 24, 2026

    start_str = start_date.isoformat()
    end_str   = end_date.isoformat()

    print(f"🌧️  Bootstrap: Fetching rainfall from {start_str} to {end_str}")
    print(f"   Stations: {len(stations)}")
    print(f"   Date range: {LOOKBACK_DAYS} days per station")
    print(f"   API calls: ~{len(stations)} (batch mode)\n")

    success = 0
    failed = 0

    for idx, station in enumerate(stations):
        sid = station["station_id"]
        try:
            # ── Fetch 60 days in one API call ─────────────────────────
            rain_data = fetch_rainfall_batch(
                station["latitude"], station["longitude"],
                start_str, end_str
            )

            if not rain_data:
                print(f"  ⚠️  Station {sid}: No rainfall data returned")
                failed += 1
                continue

            # ── Store each day's rainfall ─────────────────────────────
            for date_str, rainfall_mm in rain_data.items():
                insert_rainfall(sid, date_str, rainfall_mm)

            # ── Compute max_30d_rain ──────────────────────────────────
            rain_values = list(rain_data.values())
            rain_series = pd.Series(rain_values)

            if len(rain_series) >= 30:
                max_30d = float(rain_series.rolling(window=30).sum().max())
            else:
                max_30d = float(rain_series.sum())

            # Ensure max_30d_rain is at least a small positive value
            max_30d = max(max_30d, 1.0)
            update_max_30d_rain(sid, max_30d)

            success += 1
            if (idx + 1) % 10 == 0 or idx == 0:
                print(f"  ✅ [{idx+1}/{len(stations)}] Station {sid} | "
                      f"days={len(rain_data)} | max_30d_rain={max_30d:.1f}mm")

            # Small delay to be kind to the API
            time.sleep(0.05)

        except Exception as e:
            print(f"  ❌ Station {sid} failed: {e}")
            failed += 1
            continue

    print(f"\n{'='*60}")
    print(f"🎉 Bootstrap complete: {success} succeeded, {failed} failed")
    print(f"{'='*60}")
    print(f"\n✅ Safe to start the scheduler now.")


if __name__ == "__main__":
    bootstrap()
