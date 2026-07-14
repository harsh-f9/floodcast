"""
Backfill script for March 25-28
Iterates through each date chronologically and predicts streamflow 
for all 378 stations so that anchor data is pushed correctly.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_all_stations
from prediction_service import run_prediction_for_station

def backfill():
    dates_to_run = [
        date(2026, 3, 25),
        date(2026, 3, 26),
        date(2026, 3, 27),
        date(2026, 3, 28)
    ]
    stations = get_all_stations()
    
    for d in dates_to_run:
        print(f"\n=========================================")
        print(f"🌊 Backfilling predictions for {d.isoformat()}")
        print(f"   Stations: {len(stations)}")
        print(f"=========================================")
        success, failed = 0, 0
        for idx, s in enumerate(stations):
            sid = s["station_id"]
            try:
                res = run_prediction_for_station(sid, d)
                if (idx + 1) % 50 == 0 or idx == 0:
                    print(f"  ✅ [{idx+1}/{len(stations)}] Station {sid} -> pred={res['pred_raw_streamflow']:.2f} m³/s")
                success += 1
            except Exception as e:
                print(f"  ❌ Station {sid} failed: {e}")
                failed += 1
        print(f"✅ Finished date {d.isoformat()} (success: {success}, failed: {failed})")

if __name__ == "__main__":
    backfill()
