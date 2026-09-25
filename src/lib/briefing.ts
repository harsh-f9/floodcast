/* District briefing helper (migratable, pure — no API imports).
 * Mirrors backend/Flood_prediction/briefing.py. Delete file + modal card to remove.
 * Caller builds `meta` per station with the same threshold fallback as getPeakSeverity
 * (returnPeriodsData[station_name] ?? station.rp_*).
 */

export interface StationThresholds {
  station_name: string;
  rp_2: number;
  rp_5: number;
  rp_15: number;
  rp_20: number;
}

export interface BriefingResult {
  paragraph: string;
  counts: Record<string, number>;
  peakStation: string;
  peakFlow: number;
  peakDate: string;
  peakSeverity: string;
  rainiestWindow: string;
  action: string;
}

export function severityOf(flow: number, rp: StationThresholds): string {
  if (!rp || !rp.rp_2) return "UNKNOWN";
  if (flow < rp.rp_2) return "NORMAL";
  if (flow < rp.rp_5) return "WATCH";
  if (flow < rp.rp_15) return "WARNING";
  if (flow < rp.rp_20) return "DANGER";
  return "EXTREME";
}

function peakOf(data: any): { flow: number; date: string } {
  let flow = 0;
  let date = data?.date ?? "";
  for (const t of data?.trajectory ?? []) {
    const f = Number(t?.pred_raw_streamflow ?? 0);
    if (f > flow) {
      flow = f;
      date = t?.date ?? date;
    }
  }
  if (flow === 0 && data?.pred_raw_streamflow != null) {
    flow = Number(data.pred_raw_streamflow);
    date = data?.date ?? date;
  }
  return { flow, date };
}

export function summarizeDistrict(
  district: string,
  results: Record<number, any>,
  meta: Record<number, StationThresholds>
): BriefingResult {
  const counts: Record<string, number> = {
    NORMAL: 0,
    WATCH: 0,
    WARNING: 0,
    DANGER: 0,
    EXTREME: 0,
    UNKNOWN: 0,
  };
  let peakStation = "—";
  let peakFlow = -1;
  let peakDate = "";
  let peakSeverity = "UNKNOWN";
  const rainSum: Record<string, number> = {};
  const rainN: Record<string, number> = {};

  for (const [sidStr, data] of Object.entries(results)) {
    const sid = Number(sidStr);
    const m = meta[sid];
    if (!m) {
      counts.UNKNOWN += 1;
      continue;
    }
    const { flow, date } = peakOf(data);
    const sev = severityOf(flow, m);
    counts[sev] = (counts[sev] ?? 0) + 1;
    if (flow > peakFlow) {
      peakFlow = flow;
      peakStation = m.station_name;
      peakDate = date;
      peakSeverity = sev;
    }
    for (const r of data?.rain_window ?? []) {
      if (r?.date == null) continue;
      rainSum[r.date] = (rainSum[r.date] ?? 0) + Number(r.rainfall_mm ?? 0);
      rainN[r.date] = (rainN[r.date] ?? 0) + 1;
    }
  }

  let rainiestWindow = "";
  const days = Object.keys(rainSum);
  if (days.length) {
    const d = days.reduce((a, b) =>
      rainSum[a] / Math.max(rainN[a], 1) >= rainSum[b] / Math.max(rainN[b], 1) ? a : b
    );
    rainiestWindow = `${d} (avg ${(rainSum[d] / Math.max(rainN[d], 1)).toFixed(1)} mm)`;
  }

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  let action = "Flows normal; maintain routine monitoring.";
  if (counts.EXTREME + counts.DANGER > 0)
    action = `Prioritise ${counts.EXTREME + counts.DANGER} DANGER/EXTREME gauge(s); pre-position response.`;
  else if (counts.WARNING > 0)
    action = `Watch ${counts.WARNING} WARNING gauge(s); re-check after next rain window.`;
  else if (counts.WATCH > 0) action = "No immediate action; routine watch.";

  const paragraph =
    `${district}: ${total} gauge(s) forecast. ` +
    `Peak ${peakStation} at ${peakFlow.toFixed(1)} m3/s on ${peakDate} (${peakSeverity}). ` +
    `Severity NORMAL ${counts.NORMAL}/WATCH ${counts.WATCH}/WARNING ${counts.WARNING}/` +
    `DANGER ${counts.DANGER}/EXTREME ${counts.EXTREME}.` +
    (rainiestWindow ? ` Rainiest window ${rainiestWindow}.` : "") +
    ` ${action}`;

  return {
    paragraph,
    counts,
    peakStation,
    peakFlow: Math.round(peakFlow * 10) / 10,
    peakDate,
    peakSeverity,
    rainiestWindow,
    action,
  };
}
