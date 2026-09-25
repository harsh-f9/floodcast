import { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, X, Wrench } from "lucide-react";
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
interface Msg {
  role: "user" | "assistant";
  content: string;
  charts?: ChartPayload[];
  trace?: { tool: string; args: Record<string, unknown>; ok: boolean; error: string }[];
}

const QUICK = ["Predict Bijnor", "History of station 0", "Top 5 stations by streamflow", "Highest RP station"];

const SEV_COLOR: Record<string, string> = {
  NORMAL: "bg-emerald-500/15 text-emerald-300",
  WATCH: "bg-blue-500/15 text-blue-300",
  WARNING: "bg-amber-500/15 text-amber-300",
  DANGER: "bg-orange-500/15 text-orange-300",
  EXTREME: "bg-rose-500/15 text-rose-300",
  UNKNOWN: "bg-gray-500/15 text-gray-300",
};

function ChartCard({ c }: { c: ChartPayload }) {
  const data = (c.chart || []).map((r) => ({
    x: r.date.slice(5),
    past: r.kind === "past" ? r.streamflow : null,
    forecast: r.kind === "forecast" ? r.streamflow : null,
  }));
  const t = c.thresholds || { watch: 0, warning: 0, danger: 0, extreme: 0 };
  return (
    <div className="rounded-lg bg-white/[0.04] border border-white/10 p-2.5">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <p className="text-xs font-semibold text-gray-100 truncate">
          Stn {c.station_id}{c.district ? ` · ${c.district}` : ""}
        </p>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${SEV_COLOR[c.severity] || SEV_COLOR.UNKNOWN}`}>
          {c.severity || "UNKNOWN"}
        </span>
      </div>
      {c.peak_flow != null && (
        <p className="text-[11px] text-gray-400 mb-1.5">
          Peak {c.peak_flow} m³/s on {c.peak_date}
        </p>
      )}
      <div className="h-[140px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff14" />
            <XAxis dataKey="x" stroke="#94a3b8" fontSize={9} tickLine={false} interval="preserveStartEnd" />
            <YAxis stroke="#94a3b8" fontSize={9} tickLine={false} axisLine={false} />
            <ChartTooltip
              contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #ffffff22", borderRadius: 8, color: "#fff", fontSize: 11 }}
              formatter={(v: unknown) => [`${v} m³/s`, "Flow"]}
            />
            {t.watch > 0 && <ReferenceLine y={t.watch} stroke="#60a5fa" strokeDasharray="3 3" strokeWidth={1} />}
            {t.warning > 0 && <ReferenceLine y={t.warning} stroke="#fbbf24" strokeDasharray="3 3" strokeWidth={1} />}
            {t.danger > 0 && <ReferenceLine y={t.danger} stroke="#fb923c" strokeDasharray="3 3" strokeWidth={1} />}
            {t.extreme > 0 && <ReferenceLine y={t.extreme} stroke="#fb7185" strokeDasharray="3 3" strokeWidth={1.5} />}
            <Line type="monotone" dataKey="past" stroke="#94a3b8" strokeWidth={1.5} dot={false} connectNulls />
            <Line type="monotone" dataKey="forecast" stroke="#818cf8" strokeWidth={2} dot={{ r: 2 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function ChatSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
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
  }, [msgs, loading, open]);

  if (!open || !enabled) return null;

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || loading) return;
    const next: Msg[] = [...msgs, { role: "user", content }];
    setMsgs(next);
    setInput("");
    setLoading(true);
    try {
      const history = next
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }));
      const res = await fetch(getApiUrl("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history, horizon_days: 7 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Request failed");
      setMsgs((p) => [
        ...p,
        { role: "assistant", content: data.reply, charts: data.charts || [], trace: data.tool_trace || [] },
      ]);
    } catch (e) {
      setMsgs((p) => [...p, { role: "assistant", content: `Error: ${(e as Error).message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-[60] w-full max-w-[400px] flex flex-col bg-[#0d1117] border-l border-white/10 shadow-2xl">
      {/* Header (LibreChat-style) */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/10 bg-[#161b22]">
        <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-indigo-300" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-100 leading-tight">Flood Assistant</p>
          <p className="text-[11px] text-gray-500 truncate">
            predictions + history only{model ? ` · ${model}` : ""}
          </p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-white/10" title="Close">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3.5 py-4 flex flex-col gap-3">
        {msgs.length === 0 && (
          <div className="text-center mt-6">
            <Bot className="w-10 h-10 text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-400 mb-1">Ask for district forecasts or station history.</p>
            <p className="text-xs text-gray-600 mb-4">I can't answer anything else.</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {QUICK.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs px-2.5 py-1.5 rounded-full border border-white/15 text-gray-300 hover:bg-white/10 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${m.role === "user" ? "items-end" : "items-start"}`}>
            <div
              className={`max-w-[92%] px-3 py-2 rounded-2xl text-[13px] leading-relaxed whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-md"
                  : "bg-white/[0.06] text-gray-100 border border-white/10 rounded-bl-md"
              }`}
            >
              {m.content}
            </div>
            {m.trace && m.trace.length > 0 && (
              <details className="max-w-[92%] text-[11px] text-gray-500">
                <summary className="cursor-pointer flex items-center gap-1 hover:text-gray-300">
                  <Wrench className="w-3 h-3" /> {m.trace.length} tool call{m.trace.length > 1 ? "s" : ""}
                </summary>
                <div className="mt-1 font-mono bg-black/30 rounded-md p-2 border border-white/5">
                  {m.trace.map((t, j) => (
                    <div key={j} className={t.ok ? "text-gray-400" : "text-rose-400"}>
                      {t.ok ? "✓" : "✗"} {t.tool} {JSON.stringify(t.args)}
                      {!t.ok && t.error ? ` — ${t.error}` : ""}
                    </div>
                  ))}
                </div>
              </details>
            )}
            {m.charts && m.charts.length > 0 && (
              <div className="w-full flex flex-col gap-2">
                {m.charts.slice(0, 6).map((c) => (
                  <ChartCard key={c.station_id} c={c} />
                ))}
                {m.charts.length > 6 && (
                  <p className="text-[11px] text-gray-500">+ {m.charts.length - 6} more stations (see briefing).</p>
                )}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-[13px]">
            <Loader2 className="w-4 h-4 animate-spin" /> Running tools…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/10 bg-[#161b22]">
        <div className="flex items-center gap-2 rounded-xl bg-white/[0.05] border border-white/10 pl-3.5 pr-1.5 py-1.5 focus-within:border-indigo-500/60">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Predict Bijnor…"
            className="flex-1 bg-transparent outline-none text-sm text-gray-100 placeholder:text-gray-600"
            maxLength={500}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
