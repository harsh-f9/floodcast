import requests
import time
import json
from datetime import date, timedelta

# Update this to your deployed Render backend URL when you deploy
BACKEND_URL = "https://floodcast-backend-vx1j.onrender.com"

# Setup the dates
BOOTSTRAP_DATE = date(2026, 7, 11)  # First prediction date
LOOKBACK_DAYS = 60
start_date = BOOTSTRAP_DATE - timedelta(days=LOOKBACK_DAYS)
end_date = BOOTSTRAP_DATE - timedelta(days=1)

start_str = start_date.isoformat()
end_str = end_date.isoformat()

def fetch_rainfall_chunk(chunk):
    lats = [s["latitude"] for s in chunk]
    lons = [s["longitude"] for s in chunk]
    
    # 5 retries for this chunk
    for attempt in range(5):
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lats,
                "longitude": lons,
                "daily": "precipitation_sum",
                "start_date": start_str,
                "end_date": end_str,
                "timezone": "Asia/Kolkata"
            }, timeout=60)
            
            if r.status_code == 429:
                raise Exception("429 Too Many Requests")
            r.raise_for_status()
            
            res_list = r.json()
            if isinstance(res_list, dict):
                res_list = [res_list]
                
            chunk_data = {}
            for station, data in zip(chunk, res_list):
                sid = str(station["station_id"])
                daily = data.get("daily", {})
                times = daily.get("time", [])
                precip = daily.get("precipitation_sum", [])
                
                chunk_data[sid] = {}
                for t, p in zip(times, precip):
                    chunk_data[sid][t] = float(p) if p is not None else 0.0
                    
            return chunk_data
        except Exception as e:
            delay = 5 * (2 ** attempt)
            print(f"⚠️ Open-Meteo fetch failed ({e}). Retrying in {delay}s...")
            time.sleep(delay)
    
    print("❌ Failed completely for this chunk.")
    return {}

def run_bootstrap():
    print(f"🚀 Starting Local Bootstrap script...")
    
    # 1. Fetch all stations from backend
    try:
        res = requests.get(f"{BACKEND_URL}/stations")
        res.raise_for_status()
        stations = res.json().get("stations", [])
        print(f"✅ Fetched {len(stations)} stations from {BACKEND_URL}")
    except Exception as e:
        print(f"❌ Could not fetch stations from backend: {e}")
        return

    # 2. Chunk stations and fetch from Open-Meteo
    chunk_size = 50
    total_chunks = (len(stations) + chunk_size - 1) // chunk_size
    
    all_station_data = {}
    
    for i in range(0, len(stations), chunk_size):
        chunk = stations[i:i+chunk_size]
        print(f"🌧️ Fetching chunk {i//chunk_size + 1}/{total_chunks} from Open-Meteo...")
        chunk_data = fetch_rainfall_chunk(chunk)
        all_station_data.update(chunk_data)
        time.sleep(3) # Be nice to the API
        
    # 3. Post to backend
    print(f"\n⬆️ Pushing data for {len(all_station_data)} stations to {BACKEND_URL}...")
    try:
        res = requests.post(f"{BACKEND_URL}/api/admin/sync-rainfall", json={
            "station_data": all_station_data
        })
        res.raise_for_status()
        data = res.json()
        print(f"✅ Success! {data.get('records_inserted')} records inserted into the database.")
    except Exception as e:
        print(f"❌ Failed to sync to backend: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response:", e.response.text)

if __name__ == "__main__":
    run_bootstrap()
