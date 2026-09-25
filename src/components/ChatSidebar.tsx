import { useEffect, useRef, useState } from "react";
import { Bot, Check, Download, Loader2, Send, X, Wrench } from "lucide-react";
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
  trace?: { tool: string; args: Record<string, unknown>; ok: boolean; error: string }[];
  steps?: Step[];
  running?: boolean;
}

const QUICK = ["Predict Bijnor", "History of station 0", "Top 5 stations by streamflow", "Highest RP station"];

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
  const data = (c.chart || []).map((r) => ({
    x: r.date.slice(5),
    past: r.kind === "past" ? r.streamflow : null,
    forecast: r.kind === "forecast" ? r.streamflow : null,
  }));
  const t = c.thresholds || { watch: 0, warning: 0, danger: 0, extreme: 0 };
  return (
    <div className="rounded-lg bg-white border border-gray-200 p-2.5">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <p className="text-xs font-semibold text-black truncate">
          Stn {c.station_id}{c.district ? ` · ${c.district}` : ""}
        </p>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${SEV_STYLE[c.severity] || SEV_STYLE.UNKNOWN}`}>
          {c.severity || "UNKNOWN"}
        </span>
      </div>
      {c.peak_flow != null && (
        <p className="text-[11px] text-gray-600 mb-1.5">
          Peak {c.peak_flow} m³/s on {c.peak_date}
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
              formatter={(v: unknown) => [`${v} m³/s`, "Flow"]}
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
    ["Station ID", "Station Name", "District", "Date", "Streamflow (m3/s)", "Kind", "Severity", "Peak Flow (m3/s)", "Peak Date"],
  ];
  (m.charts || []).forEach((c) => {
    (c.chart || []).forEach((p) => {
      rows.push([
        String(c.station_id),
        c.station_name || "",
        c.district || "",
        p.date,
        p.streamflow == null ? "" : String(p.streamflow),
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
  const [model, setModel] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(getApiUrl("/api/chat/status"))
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        if (!s) return;
        setEnabled(!!s.enabled);
        setModel(s.model || "");
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
    // Non-streaming fallback (also the path when SSE is unavailable).
    const res = await fetch(getApiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history, horizon_days: 7 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Request failed");
    patchMsg(idx, (m) => ({
      ...m,
      content: data.reply,
      charts: data.charts || [],
      trace: data.tool_trace || [],
      running: false,
    }));
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
    try {
      const res = await fetch(getApiUrl("/api/chat/stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ messages: history, horizon_days: 7 }),
      });
      if (!res.ok || !res.body) throw new Error("stream unavailable");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let gotFrame = false;
      const applyEvent = (evt: any) => {
        gotFrame = true;
        switch (evt.type) {
          case "thinking":
            patchMsg(idx, (m) => ({
              ...m,
              steps: [...(m.steps || []), { id: `t${(m.steps || []).length}`, kind: "thinking", text: evt.text, running: false }],
            }));
            break;
          case "tool_start":
            patchMsg(idx, (m) => ({
              ...m,
              steps: [...(m.steps || []), { id: evt.id, kind: "tool", name: evt.name, args: evt.args, running: true }],
            }));
            break;
          case "tool_end":
            patchMsg(idx, (m) => ({
              ...m,
              steps: (m.steps || []).map((s) =>
                s.id === evt.id ? { ...s, running: false, ok: evt.ok, latencyMs: evt.latency_ms, error: evt.error || undefined } : s
              ),
            }));
            break;
          case "summary_start":
            patchMsg(idx, (m) => ({
              ...m,
              steps: [...(m.steps || []), { id: "summary", kind: "thinking", text: "Summarizing results…", running: true }],
            }));
            break;
          case "summary_done":
            patchMsg(idx, (m) => ({
              ...m,
              steps: (m.steps || []).map((s) => (s.id === "summary" ? { ...s, running: false, text: undefined } : s)),
            }));
            break;
          case "result": {
            const r = evt.result || {};
            patchMsg(idx, (m) => ({
              ...m,
              content: r.reply || "",
              charts: r.charts || [],
              trace: r.tool_trace || [],
              running: false,
            }));
            break;
          }
          case "run_error":
            patchMsg(idx, (m) => ({ ...m, content: `Error: ${evt.error || "request failed"}`, running: false }));
            break;
          default:
            break;
        }
      };
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const evt = JSON.parse(line.slice(5));
            if (evt.type === "stream_end") continue;
            applyEvent(evt);
          } catch {
            /* partial frame, ignore */
          }
        }
      }
      if (!gotFrame) await sendSync(history, idx);
    } catch (e) {
      try {
        await sendSync(history, idx);
      } catch (e2) {
        patchMsg(idx, (m) => ({ ...m, content: `Error: ${(e2 as Error).message}`, running: false }));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={embedded ? "flex flex-col h-full w-full bg-white" : "flex flex-col h-full w-full bg-white"}>
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-gray-200 bg-black">
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center">
          <Bot className="w-4 h-4 text-black" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white leading-tight">Flood Assistant</p>
          <p className="text-[11px] text-gray-400 truncate">
            predictions + history only{model ? ` · ${model}` : ""}
          </p>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10" title="Close">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3.5 py-4 flex flex-col gap-3 bg-white">
        {msgs.length === 0 && (
          <div className="text-center mt-6">
            <Bot className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-700 mb-1">Ask for district forecasts or station history.</p>
            <p className="text-xs text-gray-400 mb-4">I can't answer anything else.</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {QUICK.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs px-2.5 py-1.5 rounded-full border border-gray-300 text-gray-700 hover:bg-gray-100 transition-colors"
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
            {m.charts && m.charts.length > 0 && (
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2">
                {m.charts.map((c) => (
                  <ChartCard key={c.station_id} c={c} />
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
