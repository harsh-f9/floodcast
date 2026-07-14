import sys
import os
import time
from datetime import date

# Ensure paths correctly resolve the app models
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
from database import get_all_stations
from prediction_service import run_prediction_for_station

def start_backfill():
    stations = get_all_stations()
    dates_to_fill = [
        date(2026, 3, 25),
        date(2026, 3, 26),
        date(2026, 3, 27)
    ]
    
    total = len(stations) * len(dates_to_fill)
    count = 0
    print(f"Starting backfill mechanism for {len(stations)} stations over {len(dates_to_fill)} days.")
    print("This will process the days chronologically to properly carry over the prior day's streamflow!\n")
    
    for target_day in dates_to_fill:
        print(f"{"="*40}")
        print(f"🌊 Running batch simulations for Date: {target_day}")
        print(f"{"="*40}")
        
        success = 0
        failed = 0
        
        for station in stations:
            sid = station["station_id"]
            try:
                # Predicting day sequences organically loops previous day results from SQLite
                res = run_prediction_for_station(sid, target_day)
                success += 1
            except Exception as e:
                print(f"❌ Failed station {sid}: {e}")
                failed += 1
                
            count += 1
            if count % 50 == 0:
                print(f"  ...processed {count}/{total} total iterations.")
                
            # Sleep tiny bit to be gentle on Open-Meteo API Limits
            time.sleep(0.05)
            
        print(f"✅ Completed single-day trace for {target_day}: {success} succeeded, {failed} failed.")

if __name__ == "__main__":
    start_backfill()
