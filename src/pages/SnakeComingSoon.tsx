import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Pause, Play, RotateCcw } from "lucide-react";
import {
  PHRASE,
  PHRASE_LABEL,
  createInitialSnake,
  isOpposite,
  letterForSegment,
  spawnApple,
  stepSnake,
  type Pt,
} from "@/lib/snakeLogic";

const START_INTERVAL = 150;
const MIN_INTERVAL = 70;

type Status = "running" | "paused" | "over";

const DIRS: Record<string, Pt> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};

interface Dims {
  cols: number;
  rows: number;
  cell: number;
  w: number;
  h: number;
}

function loadBest(): number {
  try {
    return Number(localStorage.getItem("cro-snake-best") ?? 0) || 0;
  } catch {
    return 0;
  }
}

const mod = (v: number, m: number) => ((v % m) + m) % m;

// Build the body tube path, breaking it into separate subpaths wherever two
// consecutive points sit on opposite edges (edge wrap). Without the breaks,
// the tube would draw one long streak across the whole screen mid-wrap.
function buildBodyD(pts: { x: number; y: number }[], cell: number): string {
  if (pts.length === 0) return "";
  const GAP = cell * 1.5;
  let d = "";
  let run: { x: number; y: number }[] = [pts[0]];
  const flush = () => {
    if (run.length === 0) return;
    d += `M${run.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L")}`;
    if (run.length === 1) d += " l 0.01 0"; // lone point still renders as a round dot
  };
  for (let i = 1; i < pts.length; i++) {
    const a = run[run.length - 1];
    const b = pts[i];
    if (Math.hypot(b.x - a.x, b.y - a.y) > GAP) {
      flush();
      run = [b];
    } else {
      run.push(b);
    }
  }
  flush();
  return d;
}

export default function SnakeComingSoon() {
  const [snake, setSnake] = useState<Pt[]>(() => createInitialSnake());
  const [apple, setApple] = useState<Pt>(() => spawnApple(createInitialSnake(), 24, 16));
  const [status, setStatus] = useState<Status>("running");
  const [score, setScore] = useState(0);
  const [best, setBest] = useState<number>(() => loadBest());
  const [dims, setDims] = useState<Dims>({ cols: 24, rows: 16, cell: 30, w: 0, h: 0 });

  const playRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const outlineRef = useRef<SVGPathElement>(null);
  const bodyRef = useRef<SVGPathElement>(null);
  const blotchRef = useRef<SVGPathElement>(null);
  const spineRef = useRef<SVGPathElement>(null);
  const headRef = useRef<SVGGElement>(null);
  const lettersRef = useRef<SVGGElement>(null);

  const dirRef = useRef<Pt>({ x: 1, y: 0 });
  const queueRef = useRef<Pt[]>([]);
  const snakeRef = useRef(snake);
  const appleRef = useRef(apple);
  const statusRef = useRef(status);
  const scoreRef = useRef(score);
  const dimsRef = useRef(dims);
  const prevRef = useRef<Pt[] | null>(null);
  const pendingGrowthRef = useRef(0);
  const lastTickRef = useRef(0);
  const intervalRef = useRef(START_INTERVAL);
  snakeRef.current = snake;
  appleRef.current = apple;
  statusRef.current = status;
  scoreRef.current = score;
  dimsRef.current = dims;

  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const interval = Math.max(MIN_INTERVAL, START_INTERVAL - score * 3);
  intervalRef.current = interval;

  // ---- measure the full-bleed invisible grid ----
  useEffect(() => {
    const el = playRef.current;
    if (!el) return;
    const measure = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      const cell = w < 640 ? 24 : 30;
      const cols = Math.max(10, Math.floor(w / cell));
      const rows = Math.max(8, Math.floor(h / cell));
      const d = dimsRef.current;
      if (d.cols === cols && d.rows === rows && d.cell === cell) return;
      const nd = { cols, rows, cell, w, h };
      dimsRef.current = nd;
      setDims(nd);
      // keep the snake + apple on the new grid (dedupe to avoid overlap)
      const seen = new Set<string>();
      const s = snakeRef.current
        .map((p) => ({ x: mod(p.x, cols), y: mod(p.y, rows) }))
        .filter((p) => {
          const k = `${p.x},${p.y}`;
          if (seen.has(k)) return false;
          seen.add(k);
          return true;
        });
      const safe = s.length > 0 ? s : [{ x: 2, y: 1 }];
      snakeRef.current = safe;
      prevRef.current = null;
      setSnake(safe);
      const a = appleRef.current;
      if (a.x >= cols || a.y >= rows || safe.some((c) => c.x === a.x && c.y === a.y)) {
        const na = spawnApple(safe, cols, rows);
        appleRef.current = na;
        setApple(na);
      }
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const turn = useCallback((d: Pt) => {
    const last = queueRef.current.length > 0 ? queueRef.current[queueRef.current.length - 1] : dirRef.current;
    if (queueRef.current.length >= 3) return;
    if (isOpposite(d, last)) return;
    if (d.x === last.x && d.y === last.y) return;
    queueRef.current.push(d);
  }, []);

  const restart = useCallback(() => {
    const d = dimsRef.current;
    const fresh = createInitialSnake();
    dirRef.current = { x: 1, y: 0 };
    queueRef.current = [];
    prevRef.current = null;
    pendingGrowthRef.current = 0;
    lastTickRef.current = performance.now();
    snakeRef.current = fresh;
    setSnake(fresh);
    const na = spawnApple(fresh, d.cols, d.rows);
    appleRef.current = na;
    setApple(na);
    setScore(0);
    setStatus("running");
  }, []);

  const togglePause = useCallback(() => {
    setStatus((s) => (s === "running" ? "paused" : s === "paused" ? "running" : s));
  }, []);

  // ---- logical game loop (grid ticks) ----
  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => {
      if (statusRef.current !== "running") return;
      const queued = queueRef.current.shift();
      if (queued && !isOpposite(queued, dirRef.current)) {
        dirRef.current = queued;
      }
      const d = dimsRef.current;
      prevRef.current = snakeRef.current;
      lastTickRef.current = performance.now();
      const res = stepSnake(snakeRef.current, dirRef.current, appleRef.current, d.cols, d.rows);
      if (res.died) {
        setStatus("over");
        setBest((b) => {
          const nb = Math.max(b, scoreRef.current);
          try {
            localStorage.setItem("cro-snake-best", String(nb));
          } catch {
            /* ignore */
          }
          return nb;
        });
        return;
      }
      if (!res.ate && pendingGrowthRef.current > 0 && prevRef.current && prevRef.current.length > 0) {
        // eaten visually mid-tick by the render loop: regrow the popped tail
        pendingGrowthRef.current -= 1;
        res.snake.push(prevRef.current[prevRef.current.length - 1]);
      }
      snakeRef.current = res.snake;
      setSnake(res.snake);
      if (res.ate) {
        scoreRef.current += 1;
        setScore(scoreRef.current);
        const na = spawnApple(res.snake, d.cols, d.rows);
        appleRef.current = na;
        setApple(na);
      }
    }, interval);
    return () => clearInterval(id);
  }, [status, interval]);

  // ---- smooth render loop (interpolates between grid ticks) ----
  useEffect(() => {
    let raf = 0;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const d = dimsRef.current;
      if (!d.w || !svgRef.current) return;
      const curr = snakeRef.current;
      if (curr.length === 0) return;
      const prev = prevRef.current;
      const st = statusRef.current;
      let t = 1;
      if (st === "running" && prev && prev.length > 0) {
        t = Math.min(1, Math.max(0, (now - lastTickRef.current) / intervalRef.current));
      }
      const px = (p: Pt) => ({ x: (p.x + 0.5) * d.cell, y: (p.y + 0.5) * d.cell });
      const pts = curr.map((c, i) => {
        const p0 = prev?.[i];
        const b = px(c);
        if (!p0 || st !== "running") return b;
        const a = px(p0);
        // edge wrap: snap instead of streaking across the screen
        if (Math.abs(p0.x - c.x) > 1 || Math.abs(p0.y - c.y) > 1) return b;
        return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
      });
      const dAttr = buildBodyD(pts, d.cell);
      outlineRef.current?.setAttribute("d", dAttr);
      bodyRef.current?.setAttribute("d", dAttr);
      blotchRef.current?.setAttribute("d", dAttr);
      spineRef.current?.setAttribute("d", dAttr);
      // head follows the nose, rotated to the travel direction
      const head = pts[0];
      // pixel-accurate eating: what the nose visibly touches is what counts.
      // (The logical tick eats a touch early/late vs. the smooth render, which
      // made apples feel impossible to catch on the invisible grid.)
      {
        const a = appleRef.current;
        const ax = (a.x + 0.5) * d.cell;
        const ay = (a.y + 0.5) * d.cell;
        const dx = head.x - ax;
        const dy = head.y - ay;
        const r = d.cell * 0.42;
        if (statusRef.current === "running" && dx * dx + dy * dy < r * r) {
          pendingGrowthRef.current += 1;
          scoreRef.current += 1;
          setScore(scoreRef.current);
          const na = spawnApple(snakeRef.current, d.cols, d.rows);
          appleRef.current = na;
          setApple(na);
        }
      }
      const dir = dirRef.current;
      const ang = dir.x === 1 ? 0 : dir.x === -1 ? 180 : dir.y === 1 ? 90 : 270;
      headRef.current?.setAttribute("transform", `translate(${head.x.toFixed(1)} ${head.y.toFixed(1)}) rotate(${ang})`);
      // letters ride their segments (head letter sits lower, under the eye)
      const g = lettersRef.current;
      if (g) {
        const kids = g.childNodes;
        for (let i = 0; i < pts.length && i < kids.length; i++) {
          const el = kids[i] as SVGTextElement;
          el.setAttribute("x", pts[i].x.toFixed(1));
          el.setAttribute("y", (pts[i].y + (i === 0 ? d.cell * 0.2 : 0)).toFixed(1));
        }
      }
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  // Keyboard controls
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k) || e.key === " ") {
        e.preventDefault();
      }
      if (k === "arrowup" || k === "w") turn(DIRS.up);
      else if (k === "arrowdown" || k === "s") turn(DIRS.down);
      else if (k === "arrowleft" || k === "a") turn(DIRS.left);
      else if (k === "arrowright" || k === "d") turn(DIRS.right);
      else if (k === " " || k === "p") {
        if (statusRef.current !== "over") togglePause();
      } else if (k === "enter") {
        if (statusRef.current === "over") restart();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [turn, togglePause, restart]);

  const onTouchStart = (e: React.TouchEvent) => {
    const t = e.touches[0];
    touchStart.current = { x: t.clientX, y: t.clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const s = touchStart.current;
    if (!s) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - s.x;
    const dy = t.clientY - s.y;
    touchStart.current = null;
    if (Math.abs(dx) < 24 && Math.abs(dy) < 24) return;
    if (Math.abs(dx) > Math.abs(dy)) turn(dx > 0 ? DIRS.right : DIRS.left);
    else turn(dy > 0 ? DIRS.down : DIRS.up);
  };

  const { cell } = dims;
  const bodyW = cell * 0.78;
  const revealed = Math.min(snake.length, PHRASE.length);
  const initD = buildBodyD(
    snake.map((p) => ({ x: (p.x + 0.5) * cell, y: (p.y + 0.5) * cell })),
    cell
  );

  return (
    <div className="min-h-screen bg-[#eef7ff] font-sans animate-fade-in flex flex-col">
      <div className="max-w-5xl mx-auto w-full px-4 pt-12">
        <Link
          to="/projects"
          className="inline-flex items-center text-[#0a3d62] hover:text-blue-800 font-semibold mb-8 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 mr-2" />
          Back to Our Work
        </Link>

        <div className="flex flex-wrap items-center gap-4 mb-4 border-l-4 border-[#0a3d62] pl-6 py-2">
          <span className="text-4xl">🐍</span>
          <div>
            <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-[#0a3d62] uppercase leading-none">
              Snakebite Prediction
            </h1>
            <p className="text-gray-500 font-semibold mt-2 text-sm md:text-base">
              {PHRASE_LABEL} — our model is in training. Play while you wait.
            </p>
          </div>
          <span className="ml-auto bg-amber-400 text-[#0a3d62] text-xs font-black uppercase tracking-widest px-3 py-1.5 rounded-full">
            Coming Soon
          </span>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Apples", value: String(score) },
            { label: "Length", value: `${snake.length} (${snakeLettersPreview(snake.length)})` },
            { label: "Best", value: String(Math.max(best, score)) },
            { label: "Status", value: status === "running" ? "Running" : status === "paused" ? "Paused" : "Game over" },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-xl px-4 py-3 shadow-sm border border-gray-100">
              <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">{s.label}</p>
              <p className="text-lg font-black text-[#0a3d62] truncate">{s.value}</p>
            </div>
          ))}
        </div>

        {/* Phrase progress */}
        <div className="bg-white rounded-xl px-4 py-3 shadow-sm border border-gray-100 mb-6">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">
              Snake spells “{PHRASE_LABEL}” — {revealed}/{PHRASE.length} letters
            </p>
            <p className="text-xs font-black tracking-[0.2em] text-green-700">{PHRASE.split("").join(" ")}</p>
          </div>
          <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all duration-300"
              style={{ width: `${(revealed / PHRASE.length) * 100}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Starts as <b>COM</b>. Every 🍎 grows the snake by one letter — then it cycles C→O→M→I→… endlessly.
            The invisible grid spans the whole field below, edge to edge with no walls.
          </p>
        </div>
      </div>

      {/* Full-bleed invisible grid — no box, no boundary, edge to edge */}
      <div
        ref={playRef}
        data-testid="snake-board"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
        className="relative w-full overflow-hidden touch-none select-none flex-1"
        style={{ minHeight: 420, height: "52vh" }}
      >
        <svg ref={svgRef} className="absolute inset-0" width={dims.w} height={dims.h}>
          <defs>
            <linearGradient id="gmBody" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7ba23a" />
              <stop offset="55%" stopColor="#4e7320" />
              <stop offset="100%" stopColor="#31490f" />
            </linearGradient>
          </defs>
          <g strokeLinecap="round" strokeLinejoin="round" fill="none">
            <path ref={outlineRef} d={initD} stroke="#2c3a0e" strokeWidth={cell} />
            <path ref={bodyRef} d={initD} stroke="#55801f" strokeWidth={bodyW} />
            <path
              ref={blotchRef}
              d={initD}
              stroke="#33420f"
              strokeWidth={bodyW}
              strokeDasharray={`${(cell * 0.9).toFixed(1)} ${(cell * 1.1).toFixed(1)}`}
              opacity={0.55}
            />
            <path ref={spineRef} d={initD} stroke="#a4c05e" strokeWidth={Math.max(2, cell * 0.16)} opacity={0.45} />
          </g>

          {/* head with eye + flicking forked tongue, styled like the card art */}
          <g ref={headRef}>
            <circle r={cell * 0.55} fill="url(#gmBody)" stroke="#2c3a0e" strokeWidth={Math.max(2, cell * 0.07)} />
            <g transform={`translate(${(-cell * 0.05).toFixed(1)} ${(-cell * 0.26).toFixed(1)})`}>
              <g>
                <animateTransform
                  attributeName="transform"
                  type="scale"
                  values="1 1; 1 1; 1 0.1; 1 1; 1 1"
                  keyTimes="0; 0.88; 0.93; 0.98; 1"
                  dur="5s"
                  repeatCount="indefinite"
                />
                <ellipse rx={cell * 0.17} ry={cell * 0.18} fill="#f5c542" stroke="#2c3a0e" strokeWidth={Math.max(1.5, cell * 0.04)} />
                <rect x={-cell * 0.035} y={-cell * 0.15} width={cell * 0.07} height={cell * 0.3} rx={cell * 0.035} fill="#141a05" />
                <circle cx={-cell * 0.06} cy={-cell * 0.07} r={cell * 0.04} fill="#ffffff" opacity={0.9} />
              </g>
            </g>
            <g transform={`translate(${(cell * 0.52).toFixed(1)} ${(cell * 0.08).toFixed(1)})`}>
              <g>
                <animateTransform
                  attributeName="transform"
                  type="scale"
                  values="0.15; 1; 1; 0.15; 0.15"
                  keyTimes="0; 0.1; 0.5; 0.62; 1"
                  dur="3.4s"
                  repeatCount="indefinite"
                />
                <path
                  d={`M0,0 L${(cell * 0.5).toFixed(1)},${(-cell * 0.06).toFixed(1)} M${(cell * 0.5).toFixed(1)},${(-cell * 0.06).toFixed(1)} L${(cell * 0.8).toFixed(1)},${(-cell * 0.26).toFixed(1)} M${(cell * 0.5).toFixed(1)},${(-cell * 0.06).toFixed(1)} L${(cell * 0.8).toFixed(1)},${(cell * 0.14).toFixed(1)}`}
                  fill="none"
                  stroke="#d63a2f"
                  strokeWidth={Math.max(2.5, cell * 0.11)}
                  strokeLinecap="round"
                />
              </g>
            </g>
          </g>

          {/* dense bold letters riding each segment */}
          <g ref={lettersRef} fontWeight={900} fill="#ffffff" textAnchor="middle" dominantBaseline="central">
            {snake.map((p, i) => (
              <text
                key={i}
                data-testid="snake-segment"
                data-letter={letterForSegment(i)}
                x={((p.x + 0.5) * cell).toFixed(1)}
                y={((p.y + 0.5) * cell + (i === 0 ? cell * 0.2 : 0)).toFixed(1)}
                fontSize={i === 0 ? cell * 0.36 : cell * 0.55}
                stroke="#2c3a0e"
                strokeWidth={Math.max(2, cell * 0.08)}
                paintOrder="stroke"
              >
                {letterForSegment(i)}
              </text>
            ))}
          </g>
        </svg>

        {/* apple */}
        <div
          data-testid="apple"
          className="absolute left-0 top-0"
          style={{
            transform: `translate3d(${((apple.x + 0.5) * cell).toFixed(1)}px, ${((apple.y + 0.5) * cell).toFixed(1)}px, 0)`,
            width: cell,
            height: cell,
          }}
        >
          <span
            className="animate-apple-bob flex items-center justify-center w-full h-full"
            style={{ fontSize: cell * 0.95, filter: "drop-shadow(0 3px 3px rgba(10,61,98,0.3))" }}
          >
            🍎
          </span>
        </div>

        {status !== "running" && (
          <div className="absolute inset-0 bg-[#0a3d62]/70 flex flex-col items-center justify-center gap-3 text-center p-6 z-10">
            <p className="text-3xl md:text-4xl font-black text-white uppercase tracking-tight">
              {status === "paused" ? "Paused" : "Game Over"}
            </p>
            <p className="text-white/80 text-sm font-semibold">
              {status === "paused"
                ? "Press resume or hit Space to keep playing."
                : `You scored ${score} ${score === 1 ? "apple" : "apples"}. The snake spelled “${snakeLettersPreview(
                    snake.length
                  )}”.`}
            </p>
            <div className="flex gap-3">
              {status === "paused" ? (
                <button
                  onClick={togglePause}
                  className="inline-flex items-center gap-2 bg-white text-[#0a3d62] font-bold text-sm px-5 py-2.5 rounded-lg hover:bg-gray-100"
                >
                  <Play className="w-4 h-4" /> Resume
                </button>
              ) : (
                <button
                  onClick={restart}
                  className="inline-flex items-center gap-2 bg-white text-[#0a3d62] font-bold text-sm px-5 py-2.5 rounded-lg hover:bg-gray-100"
                >
                  <RotateCcw className="w-4 h-4" /> Play again
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="max-w-5xl mx-auto w-full px-4">
        <div className="flex flex-wrap items-center gap-3 mt-6">
          <button
            onClick={status === "over" ? restart : togglePause}
            className="inline-flex items-center gap-2 bg-[#0a3d62] text-white font-bold text-sm px-5 py-2.5 rounded-lg hover:bg-[#072a44]"
          >
            {status === "running" ? (
              <>
                <Pause className="w-4 h-4" /> Pause
              </>
            ) : status === "paused" ? (
              <>
                <Play className="w-4 h-4" /> Resume
              </>
            ) : (
              <>
                <RotateCcw className="w-4 h-4" /> Restart
              </>
            )}
          </button>
          {status !== "over" && (
            <button
              onClick={restart}
              className="inline-flex items-center gap-2 bg-white text-[#0a3d62] font-bold text-sm px-5 py-2.5 rounded-lg border border-gray-200 hover:bg-gray-50"
            >
              <RotateCcw className="w-4 h-4" /> Restart
            </button>
          )}
          <p className="text-xs text-gray-500 font-medium ml-auto hidden md:block">
            Arrows / WASD to steer · Space to pause · no walls, edges wrap
          </p>
        </div>

        {/* Mobile D-pad */}
        <div className="grid grid-cols-3 gap-2 w-40 mx-auto mt-6 md:hidden">
          <div />
          <button onClick={() => turn(DIRS.up)} className="bg-[#0a3d62] text-white rounded-lg py-3 font-black" aria-label="Up">
            ↑
          </button>
          <div />
          <button onClick={() => turn(DIRS.left)} className="bg-[#0a3d62] text-white rounded-lg py-3 font-black" aria-label="Left">
            ←
          </button>
          <button onClick={() => turn(DIRS.down)} className="bg-[#0a3d62] text-white rounded-lg py-3 font-black" aria-label="Down">
            ↓
          </button>
          <button onClick={() => turn(DIRS.right)} className="bg-[#0a3d62] text-white rounded-lg py-3 font-black" aria-label="Right">
            →
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-8 pb-10">
          Minimal Nokia-style demo — the full snakebite-risk model is coming soon.
        </p>
      </div>
    </div>
  );
}

function snakeLettersPreview(length: number): string {
  const out: string[] = [];
  for (let i = 0; i < length; i++) out.push(PHRASE[i % PHRASE.length]);
  return out.join("");
}
