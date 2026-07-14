# July 2024 Streamflow Batch Predictor

Predicts streamflow and flood severity for 27 gauges across all of July 2024,
using the existing LSTM+XGBoost model from the backend — without modifying any existing code.

## Usage

```powershell
# From the repo root
cd d:\crowebsite\crowebsite
.\.venv\Scripts\python.exe july2024_batch\run_july2024.py
```

## Outputs

`july2024_batch/results/`
- `july2024_predictions.csv` — one row per (gauge × day), ~837 rows
- `july2024_summary.csv` — one row per gauge with peak flow, peak date, peak severity

## Columns

### july2024_predictions.csv
| Column | Description |
|---|---|
| gauge_id | HYBAS gauge ID |
| latitude, longitude | Gauge location |
| date | Prediction date (July 2–31, 2024) |
| anchor_streamflow | Streamflow used as previous-day anchor (m³/s) |
| rainfall_mm | Observed historical rainfall from Open-Meteo Archive |
| pred_streamflow | Model-predicted streamflow (m³/s) |
| delta_m3s | Change from anchor (m³/s) |
| severity | NORMAL / WATCH / WARNING / DANGER / EXTREME |

### july2024_summary.csv
| Column | Description |
|---|---|
| gauge_id | HYBAS gauge ID |
| july1_observed | Input observed streamflow (m³/s) |
| peak_flow | Maximum predicted streamflow across July |
| peak_date | Date of peak |
| peak_severity | Severity at peak |
| rp_2, rp_5, rp_15, rp_20 | Return period thresholds used |
