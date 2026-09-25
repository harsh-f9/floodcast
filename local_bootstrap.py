"""Laptop → Render rainfall push (production ops script, standalone).

Why this exists: calling Open-Meteo for all ~367 stations at once from Render
fails with 429s, so Render never calls Open-Meteo in cron/scheduler — the laptop
fetches in small chunks and pushes via /api/admin/sync-rainfall. Keep it that way.

Rate-limit discipline (do not "optimize" without measuring):
- chunk_size 50 stations/request, 3s gap between chunks, 5 retries exp backoff.
- Server validates (400 on bad date/range); client pre-validates to fail fast.

Usage:
    python local_bootstrap.py [--backend URL] [--anchor-date YYYY-MM-DD]
        [--lookback 60] [--chunk-size 50] [--gap 3.0] [--limit 0]
        [--dry-run] [--smoke-id 0]
    Defaults: anchor = yesterday IST, window = [anchor-60, anchor-1].
    --dry-run fetches + validates but skips POST (safe to test 429 behavior).
    --limit N restricts to first N stations (e.g. --limit 2 --dry-run for smoke).
    --smoke-id S GETs /station/S after push (read-only) to confirm state.
"""
import argparse
import datetime
import sys
import os
import time

try:
    import requests
except ImportError:
    print("needs `requests`: pip install requests")
    sys.exit(2)

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

DEFAULT_BACKEND = "https://floodcast-backend-vx1j.onrender.com"


def yesterday_ist() -> datetime.date:
    return datetime.datetime.now(IST).date() - datetime.timedelta(days=1)


def valid_rain(v) -> float:
    f = float(v)
    if not (0.0 <= f <= 500.0):
        raise ValueError(f"rainfall out of range: {v}")
    return f


def fetch_rainfall_chunk(chunk, start_str, end_str, max_retries):
    lats = [s["latitude"] for s in chunk]
    lons = [s["longitude"] for s in chunk]
    for attempt in range(max_retries):
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
                chunk_data[sid] = {}
                for t, p in zip(daily.get("time", []), daily.get("precipitation_sum", [])):
                    chunk_data[sid][t] = valid_rain(p if p is not None else 0.0)
            return chunk_data
        except Exception as e:
            delay = 5 * (2 ** attempt)
            print(f"  retry {attempt + 1}/{max_retries} ({e}); waiting {delay}s...")
            time.sleep(delay)
    print("  chunk FAILED after retries (left for next run; server keeps old rows).")
    return {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Push Open-Meteo rainfall window to backend (chunked, 429-safe).")
    ap.add_argument("--backend", default=os.getenv("BACKEND_URL", DEFAULT_BACKEND))
    ap.add_argument("--anchor-date", default=None, help="Window end+1 day (default: yesterday IST)")
    ap.add_argument("--lookback", type=int, default=60)
    ap.add_argument("--chunk-size", type=int, default=50)
    ap.add_argument("--gap", type=float, default=3.0)
    ap.add_argument("--max-retries", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="First N stations only (0=all)")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + validate, skip POST")
    ap.add_argument("--smoke-id", type=int, default=None, help="GET /station/ID after push (read-only check)")
    a = ap.parse_args(argv)

    anchor = datetime.date.fromisoformat(a.anchor_date) if a.anchor_date else yesterday_ist()
    start_date = anchor - datetime.timedelta(days=a.lookback)
    start_str, end_str = start_date.isoformat(), anchor.isoformat()
    print(f"window: {start_str}..{end_str} (anchor {anchor}, lookback {a.lookback}d)")

    try:
        stations = None
        for wake in range(3):
            try:
                res = requests.get(f"{a.backend}/stations", timeout=90)
                res.raise_for_status()
                stations = res.json().get("stations", [])
                break
            except Exception as e:
                if wake < 2:
                    print(f"[WAKE] backend cold-start? retry {wake + 2}/3 in 20s ({e})")
                    time.sleep(20)
                else:
                    raise
    except Exception as e:
        print(f"[FAIL] stations fetch: {e}")
        return 1
    if a.limit > 0:
        stations = stations[:a.limit]
    print(f"[OK] {len(stations)} stations from {a.backend}")

    all_data, failed_chunks = {}, 0
    total = (len(stations) + a.chunk_size - 1) // a.chunk_size
    for i in range(0, len(stations), a.chunk_size):
        chunk = stations[i:i + a.chunk_size]
        print(f"[Fetch] chunk {i // a.chunk_size + 1}/{total}...")
        got = fetch_rainfall_chunk(chunk, start_str, end_str, a.max_retries)
        if not got:
            failed_chunks += 1
        all_data.update(got)
        time.sleep(a.gap)

    recs = sum(len(v) for v in all_data.values())
    print(f"fetched {recs} records for {len(all_data)} stations ({failed_chunks} failed chunks)")
    if a.dry_run:
        print("[DRY-RUN] skipping POST.")
        return 0 if not failed_chunks else 3

    try:
        res = requests.post(f"{a.backend}/api/admin/sync-rainfall",
                            json={"station_data": all_data}, timeout=300)
        res.raise_for_status()
        print(f"[SUCCESS] {res.json().get('records_inserted')} records inserted.")
    except Exception as e:
        print(f"[FAIL] sync: {e}")
        return 1

    if a.smoke_id is not None:
        try:
            s = requests.get(f"{a.backend}/station/{a.smoke_id}", timeout=30).json()
            print(f"[SMOKE] station {a.smoke_id}: {len(s.get('recent_predictions', []))} recent rows, "
                  f"rp_2={s.get('rp_2')} rp_20={s.get('rp_20')}")
        except Exception as e:
            print(f"[SMOKE-FAIL] {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
