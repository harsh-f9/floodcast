import requests
import csv
import sys
import os

# Update this to your deployed Render backend URL
BACKEND_URL = "https://floodcast-backend-vx1j.onrender.com"

CSV_FILE = "actuals.csv"

def upload_actuals():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Could not find '{CSV_FILE}' in the current directory.")
        print(f"Please place your GloFAS Copernicus streamflow CSV file as '{CSV_FILE}' next to this script.")
        print("The CSV must have columns: station_id, date, raw_streamflow")
        sys.exit(1)
        
    print(f"Reading {CSV_FILE}...")
    
    station_data = {}
    
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Check headers
            headers = reader.fieldnames
            if not headers:
                print("❌ CSV is empty.")
                sys.exit(1)
                
            required = ['station_id', 'date', 'raw_streamflow']
            for req in required:
                if req not in headers:
                    print(f"❌ Missing required column '{req}' in CSV header. Available headers: {headers}")
                    sys.exit(1)
                    
            row_count = 0
            for row in reader:
                sid = str(row['station_id']).strip()
                date_str = str(row['date']).strip()
                try:
                    flow_val = float(row['raw_streamflow'])
                except ValueError:
                    print(f"⚠️ Warning: Invalid streamflow value on row {row_count+2}: {row['raw_streamflow']}. Skipping.")
                    continue
                    
                if sid not in station_data:
                    station_data[sid] = {}
                station_data[sid][date_str] = flow_val
                row_count += 1
                
        print(f"Parsed {row_count} records for {len(station_data)} stations.")
    except Exception as e:
        print(f"❌ Failed to parse CSV: {e}")
        sys.exit(1)
        
    print(f"\n[Push] Pushing actual streamflow data to {BACKEND_URL}...")
    try:
        res = requests.post(f"{BACKEND_URL}/api/admin/sync-streamflow", json={
            "station_data": station_data
        })
        res.raise_for_status()
        data = res.json()
        print(f"[SUCCESS] Recalibration complete: {data.get('records_inserted')} actuals inserted into the database.")
    except Exception as e:
        print(f"[FAIL] Failed to sync streamflow actuals to backend: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response:", e.response.text)

if __name__ == "__main__":
    upload_actuals()
