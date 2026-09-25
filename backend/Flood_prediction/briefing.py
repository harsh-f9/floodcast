"""District briefing generator (migratable, pure stdlib).

One paragraph per district from master-predict data already returned:
peak station, peak flow vs RP, counts by severity, rainiest window, action line.
Delete file to remove feature. UI wiring (copy/download) is Phase 03 frontend work.

Inputs (plain dicts, no DB imports):
- results: {station_id: {trajectory:[{date,pred_raw_streamflow}], pred_raw_streamflow, date, rain_window:[{date,rainfall_mm}]}}
- meta: {station_id: {station_name, district, rp_2, rp_5, rp_15, rp_20}}
"""


def severity(flow: float, rp: dict) -> str:
    try:
        if flow < rp["rp_2"]:
            return "NORMAL"
        if flow < rp["rp_5"]:
            return "WATCH"
        if flow < rp["rp_15"]:
            return "WARNING"
        if flow < rp["rp_20"]:
            return "DANGER"
        return "EXTREME"
    except (KeyError, TypeError):
        return "UNKNOWN"


def _peak_of(data: dict) -> tuple[float, str]:
    peak, pdate = 0.0, data.get("date", "")
    for t in data.get("trajectory") or []:
        try:
            if float(t.get("pred_raw_streamflow", 0)) > peak:
                peak, pdate = float(t["pred_raw_streamflow"]), t.get("date", pdate)
        except (TypeError, ValueError):
            continue
    if peak == 0 and data.get("pred_raw_streamflow") is not None:
        try:
            peak = float(data["pred_raw_streamflow"])
            pdate = data.get("date", pdate)
        except (TypeError, ValueError):
            pass
    return peak, pdate


def summarize_district(district: str, results: dict, meta: dict) -> dict:
    counts = {"NORMAL": 0, "WATCH": 0, "WARNING": 0, "DANGER": 0, "EXTREME": 0, "UNKNOWN": 0}
    best, best_flow, best_date, best_sev = None, -1.0, "", "UNKNOWN"
    rain_sum: dict[str, float] = {}
    rain_n: dict[str, int] = {}
    for sid, data in results.items():
        m = meta.get(sid, {})
        if district != "State-wide (All Districts)" and m.get("district") != district:
            continue
        peak, pdate = _peak_of(data)
        sev = severity(peak, m) if m else "UNKNOWN"
        counts[sev] = counts.get(sev, 0) + 1
        if peak > best_flow:
            best, best_flow, best_date, best_sev = m.get("station_name", str(sid)), peak, pdate, sev
        for r in data.get("rain_window") or []:
            d = r.get("date")
            try:
                rain_sum[d] = rain_sum.get(d, 0.0) + float(r.get("rainfall_mm", 0))
                rain_n[d] = rain_n.get(d, 0) + 1
            except (TypeError, ValueError):
                continue
    rainiest = ""
    if rain_sum:
        d = max(rain_sum, key=lambda k: rain_sum[k] / max(rain_n[k], 1))
        rainiest = f"{d} (avg {rain_sum[d] / max(rain_n[d], 1):.1f} mm)"
    total = sum(counts.values())
    if counts["EXTREME"] or counts["DANGER"]:
        action = f"Prioritise {counts['EXTREME'] + counts['DANGER']} DANGER/EXTREME gauge(s); pre-position response."
    elif counts["WARNING"]:
        action = f"Watch {counts['WARNING']} WARNING gauge(s); re-check after next rain window."
    elif counts["WATCH"]:
        action = "No immediate action; routine watch."
    else:
        action = "Flows normal; maintain routine monitoring."
    para = (
        f"{district}: {total} gauge(s) forecast. "
        f"Peak {best} at {best_flow:.1f} m3/s on {best_date} ({best_sev}). "
        f"Severity NORMAL {counts['NORMAL']}/WATCH {counts['WATCH']}/WARNING {counts['WARNING']}/"
        f"DANGER {counts['DANGER']}/EXTREME {counts['EXTREME']}."
        + (f" Rainiest window {rainiest}." if rainiest else "")
        + f" {action}"
    )
    return {"district": district, "paragraph": para, "counts": counts,
            "peak_station": best, "peak_flow": round(best_flow, 1),
            "peak_date": best_date, "peak_severity": best_sev, "rainiest_window": rainiest,
            "action": action}
