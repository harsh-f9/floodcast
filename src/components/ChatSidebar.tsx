import { useEffect, useRef, useState } from "react";
import { Bot, Check, Download, Loader2, Plus, Send, X, Wrench } from "lucide-react";
import ReactMarkdown from "react-markdown";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ReferenceLine,
} from "recharts";
import { getApiUrl } from "@/lib/api";

interface ChartRow {
  date: string;
  streamflow: number | null;
  kind: string;
}
interface ChartPayload {
  station_id: number;
  station_name: string;
  district: string;
  label?: string;
  unit?: string;
  thresholds: { watch: number; warning: number; danger: number; extreme: number };
  chart: ChartRow[];
  severity: string;
  peak_flow?: number;
  peak_date?: string;
}
interface Step {
  id: string;
  kind: "thinking" | "tool";
  name?: string;
  text?: string;
  args?: Record<string, unknown>;
  ok?: boolean;
  latencyMs?: number;
  error?: string;
  running: boolean;
}
interface Msg {
  role: "user" | "assistant";
  content: string;
  charts?: ChartPayload[];
  briefing?: string;
  trace?: { tool: string; args: Record<string, unknown>; ok: boolean; error: string }[];
  steps?: Step[];
  running?: boolean;
  progress?: { done: number; total: number; note: string };
}

const SUGGESTED = [
  "Predict Bijnor",
  "Forecast for station 92",
  "Top 5 stations by streamflow",
  "Highest RP station",
  "Rainfall history of Lucknow",
  "Sweep Bijnor stations",
];

// Black-and-white severity scale: light (calm) -> black (extreme).
const SEV_STYLE: Record<string, string> = {
  NORMAL: "bg-gray-100 text-gray-700 border-gray-200",
  WATCH: "bg-gray-200 text-gray-800 border-gray-300",
  WARNING: "bg-gray-300 text-black border-gray-400",
  DANGER: "bg-black text-white border-black",
  EXTREME: "bg-black text-white border-black ring-2 ring-gray-400",
  UNKNOWN: "bg-white text-gray-500 border-gray-200",
};

function StepRow({ s }: { s: Step }) {
  if (s.kind === "thinking") {
    return (
      <details className="text-[11px] text-gray-500" open={s.running}>
        <summary className="cursor-pointer flex items-center gap-1.5 hover:text-black list-none">
          {s.running ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
          <span className="italic">Thinking{s.running ? "…" : ""}</span>
        </summary>
        {s.text && <p className="mt-1 pl-4 whitespace-pre-wrap border-l-2 border-gray-200">{s.text}</p>}
      </details>
    );
  }
  return (
    <div className="text-[11px]">
      <div className="flex items-center gap-1.5 text-gray-700">
        {s.running ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : s.ok ? (
          <Check className="w-3 h-3 text-black" />
        ) : (
          <X className="w-3 h-3 text-black" />
        )}
        <span className="font-mono font-semibold">{s.name}</span>
        {!s.running && s.latencyMs != null && <span className="text-gray-400">{s.latencyMs}ms</span>}
        {!s.running && !s.ok && <span className="font-bold">failed</span>}
      </div>
      {(s.args && Object.keys(s.args).length > 0) || s.error ? (
        <details className="mt-0.5 pl-4 text-gray-500">
          <summary className="cursor-pointer hover:text-black">details</summary>
          {s.args && Object.keys(s.args).length > 0 && (
            <pre className="mt-1 font-mono bg-gray-50 rounded p-1.5 border border-gray-200 overflow-x-auto">
              {JSON.stringify(s.args, null, 1).slice(0, 800)}
            </pre>
          )}
          {s.error && <p className="mt-1 font-semibold text-black">{s.error}</p>}
        </details>
      ) : null}
    </div>
  );
}

function ChartCard({ c }: { c: ChartPayload }) {
  const unit = c.unit || "m³/s";
  const data = (c.chart || []).map((r) => ({
    x: (r.date || "").slice(5),
    past: r.kind === "past" ? r.streamflow : null,
    forecast: r.kind === "forecast" ? r.streamflow : null,
  }));
  const t = c.thresholds || { watch: 0, warning: 0, danger: 0, extreme: 0 };
  const title = c.label || `Stn ${c.station_id}${c.district ? ` · ${c.district}` : ""}`;
  return (
    <div className="rounded-lg bg-white border border-gray-200 p-2.5">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <p className="text-xs font-semibold text-black truncate">
          {title}
        </p>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${SEV_STYLE[c.severity] || SEV_STYLE.UNKNOWN}`}>
          {c.severity || "UNKNOWN"}
        </span>
      </div>
      {c.peak_flow != null && (
        <p className="text-[11px] text-gray-600 mb-1.5">
          Peak {c.peak_flow} {unit} on {c.peak_date}
        </p>
      )}
      <div className="h-[140px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
            <XAxis dataKey="x" stroke="#737373" fontSize={9} tickLine={false} interval="preserveStartEnd" />
            <YAxis stroke="#737373" fontSize={9} tickLine={false} axisLine={false} />
            <ChartTooltip
              contentStyle={{ backgroundColor: "#fff", border: "1px solid #d4d4d4", borderRadius: 8, color: "#000", fontSize: 11 }}
              formatter={(v: unknown) => [`${v} ${unit}`, unit === "mm" ? "Rain" : "Flow"]}
            />
            {t.watch > 0 && <ReferenceLine y={t.watch} stroke="#a3a3a3" strokeDasharray="3 3" strokeWidth={1} />}
            {t.warning > 0 && <ReferenceLine y={t.warning} stroke="#737373" strokeDasharray="3 3" strokeWidth={1} />}
            {t.danger > 0 && <ReferenceLine y={t.danger} stroke="#404040" strokeDasharray="3 3" strokeWidth={1} />}
            {t.extreme > 0 && <ReferenceLine y={t.extreme} stroke="#000" strokeDasharray="3 3" strokeWidth={1.5} />}
            <Line type="monotone" dataKey="past" stroke="#a3a3a3" strokeWidth={1.5} dot={false} connectNulls />
            <Line type="monotone" dataKey="forecast" stroke="#000" strokeWidth={2} dot={{ r: 2 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Same quoting pattern as the dashboard's Master Predict CSV export.
function exportMessageCsv(m: Msg, idx: number) {
  const rows: string[][] = [
    ["Station ID", "Station Name", "District", "Date", "Value", "Unit", "Kind", "Severity", "Peak Value", "Peak Date"],
  ];
  (m.charts || []).forEach((c) => {
    (c.chart || []).forEach((p) => {
      rows.push([
        c.station_id === -1 ? "" : String(c.station_id),
        c.label || c.station_name || "",
        c.district || "",
        p.date,
        p.streamflow == null ? "" : String(p.streamflow),
        c.unit || "m³/s",
        p.kind,
        c.severity || "",
        c.peak_flow == null ? "" : String(c.peak_flow),
        c.peak_date || "",
      ]);
    });
  });
  if (rows.length === 1) rows.push(["Response", m.content]);
  const csvContent =
    "data:text/csv;charset=utf-8," +
    rows.map((e) => e.map((val) => `"${String(val).replace(/"/g, '""')}"`).join(",")).join("\n");
  const link = document.createElement("a");
  link.setAttribute("href", encodeURI(csvContent));
  link.setAttribute("download", `Chat_Response_${idx + 1}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default function ChatSidebar({ embedded, onClose }: { embedded?: boolean; onClose?: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const newChat = () => {
    // Backend is stateless (history travels with each request), so clearing
    // the UI thread also clears everything the model sees.
    setMsgs([]);
    setInput("");
  };

  useEffect(() => {
    fetch(getApiUrl("/api/chat/status"))
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        if (!s) return;
        setEnabled(!!s.enabled);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, loading]);

  if (!enabled) return null;

  const patchMsg = (idx: number, fn: (m: Msg) => Msg) =>
    setMsgs((p) => p.map((m, j) => (j === idx ? fn(m) : m)));

  const sendSync = async (history: { role: string; content: string }[], idx: number) => {
    // Non-streaming fallback (also the path when jobs are unavailable).
    const res = await fetch(getApiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history, horizon_days: 7 }),
    });
    let data: any = null;
    try {
      data = await res.json();
    } catch {
      throw new Error(`Request failed (HTTP ${res.status})`);
    }
    if (!res.ok) throw new Error(data?.detail || `Request failed (HTTP ${res.status})`);
    patchMsg(idx, (m) => ({
      ...m,
      content: data.reply,
      charts: data.charts || [],
      briefing: data.briefing || undefined,
      trace: data.tool_trace || [],
      running: false,
    }));
  };

  const stepsFromEvents = (events: any[]): Step[] => {
    const steps: Step[] = [];
    const byId = new Map<string, Step>();
    events.forEach((evt, i) => {
      if (evt.type === "thinking") {
        steps.push({ id: `t${i}`, kind: "thinking", text: evt.text, running: false });
      } else if (evt.type === "tool_start") {
        const s: Step = { id: evt.id, kind: "tool", name: evt.name, args: evt.args, running: true };
        byId.set(evt.id, s);
        steps.push(s);
      } else if (evt.type === "tool_end") {
        const s = byId.get(evt.id);
        if (s) {
          s.running = false;
          s.ok = evt.ok;
          s.latencyMs = evt.latency_ms;
          s.error = evt.error || undefined;
        } else {
          steps.push({ id: evt.id, kind: "tool", name: evt.name || "tool", running: false, ok: evt.ok, error: evt.error || undefined });
        }
      } else if (evt.type === "summary_start") {
        const s: Step = { id: "summary", kind: "thinking", text: "Summarizing results…", running: true };
        byId.set("summary", s);
        steps.push(s);
      } else if (evt.type === "summary_done") {
        const s = byId.get("summary");
        if (s) {
          s.running = false;
          s.text = undefined;
        }
      }
    });
    return steps;
  };

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || loading) return;
    const next: Msg[] = [...msgs, { role: "user", content }];
    setMsgs(next);
    setInput("");
    setLoading(true);
    const history = next
      .filter((m) => m.role === "user" || m.role === "assistant")
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));
    const idx = next.length; // assistant placeholder position
    setMsgs((p) => [...p, { role: "assistant", content: "", steps: [], running: true }]);
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    try {
      // Background job first: survives multi-minute sweeps; poll for timeline.
      const sub = await fetch(getApiUrl("/api/chat/jobs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, horizon_days: 7 }),
      });
      if (!sub.ok) throw new Error("jobs unavailable");
      const { job_id } = await sub.json();
      let fails = 0;
      const deadline = Date.now() + 10 * 60 * 1000;
      for (;;) {
        await sleep(1500);
        let st: any;
        try {
          const pr = await fetch(getApiUrl(`/api/chat/jobs/${job_id}`));
          if (!pr.ok) throw new Error("poll failed");
          st = await pr.json();
        } catch {
          if (++fails > 8) throw new Error("lost contact with background job");
          continue;
        }
        fails = 0;
        patchMsg(idx, (m) => ({
          ...m,
          steps: stepsFromEvents(st.events || []),
          progress: { done: st.progress_done || 0, total: st.progress_total || 0, note: st.progress_note || "" },
        }));
        if (st.status === "done") {
          const r = st.result || {};
          patchMsg(idx, (m) => ({
            ...m,
            content: r.reply || "",
            charts: r.charts || [],
            briefing: r.briefing || undefined,
            trace: r.tool_trace || [],
            running: false,
            progress: undefined,
          }));
          break;
        }
        if (st.status === "failed" || st.status === "cancelled") {
          patchMsg(idx, (m) => ({ ...m, content: `Error: ${st.error || `job ${st.status}`}`, running: false, progress: undefined }));
          break;
        }
        if (Date.now() > deadline) {
          patchMsg(idx, (m) => ({
            ...m,
            content: `${m.content ? m.content + "\n\n" : ""}Still running in the background (job ${job_id}) — it keeps its progress; ask again later for the result.`,
            running: false,
            progress: undefined,
          }));
          break;
        }
      }
    } catch (e) {
      // Sync fallback ONLY when the job never started (submit failed).
      // Never re-run after a successful submit: the job keeps running.
      if ((e as Error).message === "jobs unavailable") {
        try {
          await sendSync(history, idx);
        } catch (e2) {
          patchMsg(idx, (m) => ({ ...m, content: `Error: ${(e2 as Error).message}`, running: false, progress: undefined }));
        }
      } else {
        patchMsg(idx, (m) => ({ ...m, content: `Error: ${(e as Error).message}`, running: false, progress: undefined }));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={embedded ? "flex flex-col h-full w-full bg-white" : "flex flex-col h-full w-full bg-white"}>
      {/* Header */}
      <div className="relative flex items-center justify-center gap-2.5 px-4 py-4 border-b border-gray-200 bg-black">
        <div className="w-9 h-9 rounded-full bg-white flex items-center justify-center shrink-0">
          <Bot className="w-5 h-5 text-black" />
        </div>
        <p className="text-xl font-bold text-white leading-tight tracking-tight">Flood Assistant</p>
        <div className="absolute right-3 flex items-center gap-1">
          <button onClick={newChat} className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10" title="New chat">
            <Plus className="w-4 h-4" />
          </button>
          {onClose && (
            <button onClick={onClose} className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10" title="Close">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3.5 py-4 flex flex-col gap-3 bg-white">
        {msgs.length === 0 && (
          <div className="text-center mt-6">
            <Bot className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-700 mb-1">Ask for forecasts, history, or analytics.</p>
            <p className="text-xs text-gray-400 mb-4">I can't answer anything else.</p>
            <div className="grid grid-cols-3 gap-2">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="aspect-square rounded-2xl border border-gray-300 text-gray-700 hover:bg-gray-100 hover:border-black transition-colors text-[11px] font-semibold leading-tight p-2 flex items-center justify-center"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${m.role === "user" ? "items-end" : "items-start"}`}>
            {(m.content || m.role === "user") && (
            <div
              className={`max-w-[95%] px-3 py-2 rounded-2xl text-[13px] leading-relaxed ${
                m.role === "user"
                  ? "bg-black text-white rounded-br-md"
                  : "bg-gray-100 text-black border border-gray-200 rounded-bl-md"
              }`}
            >
              {m.role === "assistant" ? (
                <div className="[&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_strong]:font-bold [&_code]:bg-gray-200 [&_code]:px-1 [&_code]:rounded [&_code]:text-[12px] [&_h1]:font-bold [&_h2]:font-bold [&_h3]:font-bold [&_h1]:mb-1 [&_h2]:mb-1 [&_h3]:mb-1 [&_a]:underline">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span className="whitespace-pre-wrap">{m.content}</span>
              )}
            </div>
            )}
            {m.role === "assistant" && m.steps && m.steps.length > 0 && (
              <div className="w-full max-w-[95%] flex flex-col gap-1 rounded-xl border border-gray-200 bg-white px-2.5 py-2">
                {m.steps.map((s) => (
                  <StepRow key={s.id} s={s} />
                ))}
              </div>
            )}
            {m.running && m.progress && m.progress.total > 0 && (
              <div className="w-full max-w-[95%]">
                <div className="h-1.5 rounded-full bg-gray-200 overflow-hidden">
                  <div
                    className="h-full bg-black transition-all"
                    style={{ width: `${Math.min(100, Math.round((m.progress.done / m.progress.total) * 100))}%` }}
                  />
                </div>
                <p className="text-[11px] text-gray-500 mt-1">
                  {m.progress.done}/{m.progress.total} stations{m.progress.note ? ` · ${m.progress.note}` : ""}
                </p>
              </div>
            )}
            {m.role === "assistant" && (
              <button
                onClick={() => exportMessageCsv(m, i)}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-gray-500 hover:text-black border border-gray-200 hover:border-black rounded-md px-2 py-1 transition-colors"
                title="Export this response to CSV"
              >
                <Download className="w-3 h-3" /> Export CSV
              </button>
            )}
            {m.trace && m.trace.length > 0 && (
              <details className="max-w-[95%] text-[11px] text-gray-500">
                <summary className="cursor-pointer flex items-center gap-1 hover:text-black">
                  <Wrench className="w-3 h-3" /> {m.trace.length} tool call{m.trace.length > 1 ? "s" : ""}
                </summary>
                <div className="mt-1 font-mono bg-gray-50 rounded-md p-2 border border-gray-200">
                  {m.trace.map((t, j) => (
                    <div key={j} className={t.ok ? "text-gray-600" : "text-black font-bold"}>
                      {t.ok ? "✓" : "✗"} {t.tool} {JSON.stringify(t.args)}
                      {!t.ok && t.error ? ` — ${t.error}` : ""}
                    </div>
                  ))}
                </div>
              </details>
            )}
            {m.briefing && (
              <div className="w-full max-w-[95%] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 mb-1">District briefing</p>
                <p className="text-[12px] leading-relaxed text-black">{m.briefing}</p>
              </div>
            )}
            {m.charts && m.charts.length > 0 && (
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2">
                {m.charts.map((c, j) => (
                  <ChartCard key={`${c.station_id}-${c.label || c.district || ""}-${j}`} c={c} />
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-gray-500 text-[13px]">
            <Loader2 className="w-4 h-4 animate-spin" /> Running tools…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-200 bg-white">
        <div className="flex items-center gap-2 rounded-xl bg-gray-50 border border-gray-200 pl-3.5 pr-1.5 py-1.5 focus-within:border-black">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Predict Bijnor…"
            className="flex-1 bg-transparent outline-none text-sm text-black placeholder:text-gray-400"
            maxLength={500}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="p-2 rounded-lg bg-black text-white hover:bg-gray-800 disabled:opacity-40 transition-colors"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
