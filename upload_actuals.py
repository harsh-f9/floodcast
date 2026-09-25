import requests
import csv
import sys
import os

# Update this to your deployed backend URL (Render or Vercel)
# Can also be passed via command line argument: python upload_actuals.py https://your-app.vercel.app
DEFAULT_BACKEND = "https://floodcast-backend-vx1j.onrender.com"
BACKEND_URL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BACKEND_URL", DEFAULT_BACKEND)

CSV_FILE = "actuals.csv"


def load_long_csv(path):
    """Long format: station_id,date,raw_streamflow rows. Returns {sid: {date: flow}}."""
    import csv as _csv

    station_data = {}
    with open(path, mode='r', encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            print("CSV is empty.")
            sys.exit(1)
        for req in ['station_id', 'date', 'raw_streamflow']:
            if req not in headers:
                print(f"Missing required column '{req}'. Headers: {headers}")
                sys.exit(1)
        row_count = 0
        for row in reader:
            sid = str(row['station_id']).strip()
            date_str = str(row['date']).strip()
            try:
                flow_val = float(row['raw_streamflow'])
            except ValueError:
                print(f"Warning: bad streamflow on row {row_count + 2}, skipping.")
                continue
            station_data.setdefault(sid, {})[date_str] = flow_val
            row_count += 1
    print(f"Parsed {row_count} records for {len(station_data)} stations (long CSV).")
    return station_data


def load_sync_json(path):
    """Nested format from baseflow_glofas.py: {station_id: {date: flow}}."""
    import json as _json
    from datetime import date as _date

    with open(path, encoding='utf-8') as f:
        raw = _json.load(f)
    station_data, skipped = {}, 0
    for sid, dated in raw.items():
        if not isinstance(dated, dict):
            skipped += 1
            continue
        for date_str, flow_val in dated.items():
            try:
                _date.fromisoformat(date_str)
                flow = float(flow_val)
            except (ValueError, TypeError):
                skipped += 1
                continue
            station_data.setdefault(str(sid), {})[date_str] = flow
    print(f"Parsed {sum(len(v) for v in station_data.values())} records "
          f"for {len(station_data)} stations (sync JSON, {skipped} skipped).")
    return station_data

def upload_actuals(input_path=None):
    path = input_path or (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("http") else None) or CSV_FILE
    # Backend URL may be argv[1] (legacy) or argv[2] when input path is given.
    backend = DEFAULT_BACKEND
    for arg in sys.argv[1:]:
        if arg.startswith("http"):
            backend = arg
    backend = os.getenv("BACKEND_URL", backend)

    if not os.path.exists(path):
        print(f"Could not find '{path}' in the current directory.")
        print("Provide long CSV (station_id,date,raw_streamflow) as 'actuals.csv',")
        print("or nested sync JSON from baseflow_glofas.py (deploy/baseflow/sync_*.json).")
        sys.exit(1)

    print(f"Reading {path}...")
    if path.endswith(".json"):
        station_data = load_sync_json(path)
    else:
        station_data = load_long_csv(path)
        
    print(f"\n[Push] Pushing actual streamflow data to {BACKEND_URL}...")
    try:
        res = requests.post(f"{backend}/api/admin/sync-streamflow", json={
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
