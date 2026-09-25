"""GloFAS base-streamflow fetcher (migratable, standalone).

Adapts `downloading base streamflow data/script used in colab to download for 22 sept.py`
to production: coords from frozen `deploy/gauges_info.csv` (not Drive),
date defaults to previous day IST, outputs versioned under `deploy/baseflow/`.

Migratable: stdlib-only on import. pandas/xarray/cdsapi imported lazily inside
functions, so --help and coord checks work without heavy deps. No imports from
database/prediction_service at top level. Delete this file + deploy/baseflow/
to remove the feature with zero impact on inference.

Outputs (per date D=YYYY-MM-DD):
- deploy/baseflow/extracted_streamflow_YYYY_MM_DD.csv (audit, colab naming)
  cols: gauge_id,latitude,longitude,streamflow_m3s (+ passthrough statics if present)
- deploy/baseflow/sync_streamflow_YYYY-MM-DD.json (ready for POST /api/admin/sync-streamflow)
  {station_id: {D: flow}} with stable IDs = deploy order index, EXCLUDED_11 skipped.

Usage:
    python -m Flood_prediction.baseflow_glofas --date 2026-09-24
    python -m Flood_prediction.baseflow_glofas  # yesterday IST
    python -m Flood_prediction.baseflow_glofas --from-csv "downloading base streamflow data/extracted_streamflow_2026_09_22.csv" --date 2026-09-22
    python -m Flood_prediction.baseflow_glofas --list-coords  # stdlib check, no deps

Env:
    CDS_API_KEY (or existing ~/.cdsapirc). Never hardcode keys.
"""

import argparse
import csv
import datetime
import json
import os
import sys

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))  # no tzdata on Windows

DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")
GAUGES_CSV = os.path.join(DEPLOY_DIR, "gauges_info.csv")
BASEFLOW_DIR = os.path.join(DEPLOY_DIR, "baseflow")

# Keep in sync with validation.EXCLUDED_11, but do not import at top (migratable).
EXCLUDED_11 = frozenset({
    "hybas_4121486100", "hybas_4120878420", "hybas_4120888940",
    "hybas_4121472500", "hybas_4120878430", "hybas_4120888130",
    "hybas_4120881440", "hybas_4120854010", "hybas_4121445720",
    "hybas_4120889880", "hybas_4120855950",
})


def get_target_date(explicit: str | None = None) -> datetime.date:
    """Previous date IST by default (GloFAS intermediate latency)."""
    if explicit:
        return datetime.date.fromisoformat(explicit)
    return datetime.datetime.now(IST).date() - datetime.timedelta(days=1)


def load_gauge_coords(gauges_csv: str = GAUGES_CSV) -> list[dict]:
    """Stdlib CSV load: [{gauge_id, latitude, longitude, idx}]. idx = stable station_id."""
    rows = []
    with open(gauges_csv, newline="") as f:
        for idx, row in enumerate(csv.DictReader(f)):
            gid = row.get("gauge_id")
            if not gid or gid in EXCLUDED_11:
                continue
            rows.append({
                "gauge_id": gid,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "station_id": idx,  # stable: deploy order index, matches seed_db
            })
    if not rows:
        raise ValueError(f"no gauges loaded from {gauges_csv}")
    return rows


def bbox(rows: list[dict], pad: float = 0.1) -> tuple[float, float, float, float]:
    lats = [r["latitude"] for r in rows]
    lons = [r["longitude"] for r in rows]
    return (round(max(lats) + pad, 4), round(min(lats) - pad, 4),
            round(max(lons) + pad, 4), round(min(lons) - pad, 4))  # north,south,east,west


def ensure_cds_config() -> None:
    """Respect existing ~/.cdsapirc; else build from CDS_API_KEY env. Raise with instructions."""
    rc = os.path.expanduser("~/.cdsapirc")
    if os.path.exists(rc):
        return
    key = os.environ.get("CDS_API_KEY")
    if not key:
        raise RuntimeError(
            "CDS credentials missing: set CDS_API_KEY env or create ~/.cdsapirc "
            "with 'url: https://ewds.climate.copernicus.eu/api' + 'key: <key>'."
        )
    with open(rc, "w") as f:
        f.write("url: https://ewds.climate.copernicus.eu/api\n")
        f.write(f"key: {key}\n")


def download_glofas(target: datetime.date, north: float, south: float,
                    east: float, west: float, workdir: str) -> str:
    """Lazy-import cdsapi. Returns zip path."""
    import cdsapi  # heavy, lazy for migratability

    ensure_cds_config()
    y, m, d = f"{target.year:04d}", f"{target.month:02d}", f"{target.day:02d}"
    zip_path = os.path.join(workdir, f"glofas_data_{y}{m}{d}.zip")
    c = cdsapi.Client()
    c.retrieve(
        "cems-glofas-historical",
        {
            "system_version": ["version_4_0"],
            "hydrological_model": ["lisflood"],
            "product_type": ["intermediate"],
            "timespan": ["time_mean"],
            "variable": ["average_river_discharge_in_the_last_24_hours"],
            "year": [y], "month": [m], "day": [d],
            "data_format": "grib2",
            "download_format": "zip",
            "area": [north, west, south, east],
        },
        zip_path,
    )
    return zip_path


def extract_flows(zip_path: str, rows: list[dict], workdir: str) -> str:
    """Lazy-import xarray/cfgrib/pandas. Returns extracted grib path (for debug)."""
    import glob
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(workdir)
    gribs = glob.glob(os.path.join(workdir, "*.grib*"))
    if not gribs:
        raise FileNotFoundError("No GRIB file inside downloaded archive")
    return gribs[0]


def map_flows(grib_path: str, rows: list[dict]) -> dict[str, float]:
    """Nearest-neighbor mapping. Lazy xarray. Returns {gauge_id: flow}."""
    import xarray as xr  # needs cfgrib engine installed

    ds = xr.open_dataset(grib_path, engine="cfgrib")
    try:
        var = list(ds.data_vars)[0]
        out = {}
        for r in rows:
            try:
                val = ds[var].sel(latitude=r["latitude"], longitude=r["longitude"], method="nearest")
                out[r["gauge_id"]] = float(val.values)
            except Exception:
                out[r["gauge_id"]] = float("nan")
        return out
    finally:
        ds.close()


def save_outputs(target: datetime.date, rows: list[dict], flows: dict[str, float]) -> tuple[str, str]:
    """Write audit CSV + sync JSON under deploy/baseflow/. Returns (csv_path, json_path)."""
    import math

    os.makedirs(BASEFLOW_DIR, exist_ok=True)
    ymd = target.strftime("%Y_%m_%d")
    iso = target.isoformat()
    csv_path = os.path.join(BASEFLOW_DIR, f"extracted_streamflow_{ymd}.csv")
    json_path = os.path.join(BASEFLOW_DIR, f"sync_streamflow_{iso}.json")

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gauge_id", "latitude", "longitude", "streamflow_m3s"])
        for r in rows:
            v = flows.get(r["gauge_id"], float("nan"))
            w.writerow([r["gauge_id"], r["latitude"], r["longitude"],
                        "" if isinstance(v, float) and math.isnan(v) else v])

    payload: dict[str, dict[str, float]] = {}
    for r in rows:
        v = flows.get(r["gauge_id"])
        if v is None or (isinstance(v, float) and (math.isnan(v) or v < 0)):
            continue  # skip NaN/negative: never fabricate 0.0 anchor (see seed W6)
        payload[str(r["station_id"])] = {iso: float(v)}
    with open(json_path, "w") as f:
        json.dump(payload, f)
    return csv_path, json_path


def convert_existing_csv(csv_path: str, target: datetime.date) -> tuple[str, str]:
    """Manual-CSV path (user's Copernicus workflow): convert any extracted CSV to sync JSON.

    Accepts colab headers (gauge_id,latitude_x,longitude_x,streamflow_m3s) or
    audit headers (gauge_id,latitude,longitude,streamflow_m3s).
    """
    flows: dict[str, float] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        lat_key = "latitude_x" if "latitude_x" in (reader.fieldnames or []) else "latitude"
        lon_key = "longitude_x" if "longitude_x" in (reader.fieldnames or []) else "longitude"
        for row in reader:
            gid = row.get("gauge_id") or row.get("Gauge_ID")
            if not gid or gid in EXCLUDED_11:
                continue
            try:
                flows[gid] = float(row["streamflow_m3s"])
            except (KeyError, ValueError, TypeError):
                continue
    rows = load_gauge_coords()
    # Keep only gauges present in CSV (manual file may be 378 incl excluded)
    rows = [r for r in rows if r["gauge_id"] in flows]
    return save_outputs(target, rows, flows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch GloFAS base streamflow for previous date.")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: yesterday IST)")
    p.add_argument("--from-csv", default=None, help="Convert existing extracted CSV instead of downloading")
    p.add_argument("--list-coords", action="store_true", help="Print gauge count + bbox, no download")
    p.add_argument("--workdir", default=None, help="Temp dir for zip/grib (default: deploy/baseflow/tmp)")
    args = p.parse_args(argv)

    target = get_target_date(args.date)
    rows = load_gauge_coords()
    if args.list_coords:
        n, s, e, w = bbox(rows)
        print(f"gauges(367-filtered): {len(rows)} bbox N{n} S{s} E{e} W{w} target={target.isoformat()}")
        return 0

    if args.from_csv:
        csv_path, json_path = convert_existing_csv(args.from_csv, target)
        print(f"converted {args.from_csv} -> {csv_path} + {json_path}")
        print(f"POST {json_path} to /api/admin/sync-streamflow to anchor predictions.")
        return 0

    north, south, east, west = bbox(rows)
    workdir = args.workdir or os.path.join(BASEFLOW_DIR, "tmp", target.strftime("%Y%m%d"))
    os.makedirs(workdir, exist_ok=True)
    print(f"target={target.isoformat()} gauges={len(rows)} area N{north} W{west} S{south} E{east}")
    zip_path = download_glofas(target, north, south, east, west, workdir)
    grib_path = extract_flows(zip_path, rows, workdir)
    flows = map_flows(grib_path, rows)
    csv_path, json_path = save_outputs(target, rows, flows)
    print(f"saved {csv_path} + {json_path}")
    print(f"POST {json_path} to /api/admin/sync-streamflow to anchor predictions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
