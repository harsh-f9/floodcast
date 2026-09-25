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

const COLS = 24;
const ROWS = 16;
const START_INTERVAL = 150;
const MIN_INTERVAL = 70;

type Status = "running" | "paused" | "over";

const DIRS: Record<string, Pt> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};

function loadBest(): number {
  try {
    return Number(localStorage.getItem("cro-snake-best") ?? 0) || 0;
  } catch {
    return 0;
  }
}

export default function SnakeComingSoon() {
  const [snake, setSnake] = useState<Pt[]>(() => createInitialSnake());
  const [apple, setApple] = useState<Pt>(() => spawnApple(createInitialSnake(), COLS, ROWS));
  const [status, setStatus] = useState<Status>("running");
  const [score, setScore] = useState(0);
  const [best, setBest] = useState<number>(() => loadBest());

  const dirRef = useRef<Pt>({ x: 1, y: 0 });
  const queueRef = useRef<Pt[]>([]);
  const snakeRef = useRef(snake);
  const appleRef = useRef(apple);
  const statusRef = useRef(status);
  const scoreRef = useRef(score);
  snakeRef.current = snake;
  appleRef.current = apple;
  statusRef.current = status;
  scoreRef.current = score;

  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const interval = Math.max(MIN_INTERVAL, START_INTERVAL - score * 3);

  const turn = useCallback((d: Pt) => {
    const last = queueRef.current.length > 0 ? queueRef.current[queueRef.current.length - 1] : dirRef.current;
    if (queueRef.current.length >= 3) return;
    if (isOpposite(d, last)) return;
    if (d.x === last.x && d.y === last.y) return;
    queueRef.current.push(d);
  }, []);

  const restart = useCallback(() => {
    const fresh = createInitialSnake();
    dirRef.current = { x: 1, y: 0 };
    queueRef.current = [];
    setSnake(fresh);
    setApple(spawnApple(fresh, COLS, ROWS));
    setScore(0);
    setStatus("running");
  }, []);

  const togglePause = useCallback(() => {
    setStatus((s) => (s === "running" ? "paused" : s === "paused" ? "running" : s));
  }, []);

  // Game loop
  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => {
      if (statusRef.current !== "running") return;
      const queued = queueRef.current.shift();
      if (queued && !isOpposite(queued, dirRef.current)) {
        dirRef.current = queued;
      }
      const res = stepSnake(snakeRef.current, dirRef.current, appleRef.current, COLS, ROWS);
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
      setSnake(res.snake);
      if (res.ate) {
        setScore((s) => s + 1);
        setApple(spawnApple(res.snake, COLS, ROWS));
      }
    }, interval);
    return () => clearInterval(id);
  }, [status, interval]);

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

  // Map cells -> segment index for O(1) render lookup
  const segIndex = new Map<string, number>();
  snake.forEach((c, i) => segIndex.set(`${c.x},${c.y}`, i));

  const cells = [];
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const key = `${x},${y}`;
      const si = segIndex.get(key);
      const isApple = apple.x === x && apple.y === y;
      if (si !== undefined) {
        const isHead = si === 0;
        cells.push(
          <div
            key={key}
            data-testid="snake-segment"
            data-letter={letterForSegment(si)}
            title={letterForSegment(si)}
            className={`flex items-center justify-center rounded-[4px] font-bold select-none ${
              isHead ? "bg-green-700 text-white" : "bg-green-500 text-white"
            } text-[10px] sm:text-xs md:text-sm leading-none`}
          >
            {letterForSegment(si)}
          </div>
        );
      } else if (isApple) {
        cells.push(
          <div
            key={key}
            data-testid="apple"
            className="flex items-center justify-center rounded-[4px] bg-white select-none text-sm sm:text-base md:text-lg leading-none"
          >
            🍎
          </div>
        );
      } else {
        cells.push(<div key={key} className="rounded-[4px] bg-white" />);
      }
    }
  }

  const revealed = Math.min(snake.length, PHRASE.length);

  return (
    <div className="min-h-screen bg-[#eef7ff] py-12 px-4 animate-fade-in font-sans">
      <div className="max-w-5xl mx-auto">
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
            Endless box: crossing any edge wraps around.
          </p>
        </div>

        {/* Board */}
        <div className="relative">
          <div
            data-testid="snake-board"
            onTouchStart={onTouchStart}
            onTouchEnd={onTouchEnd}
            className="grid gap-[2px] bg-[#d7e3ee] p-[6px] rounded-2xl shadow-xl touch-none select-none"
            style={{
              gridTemplateColumns: `repeat(${COLS}, 1fr)`,
              aspectRatio: `${COLS} / ${ROWS}`,
            }}
          >
            {cells}
          </div>

          {status !== "running" && (
            <div className="absolute inset-0 rounded-2xl bg-[#0a3d62]/70 flex flex-col items-center justify-center gap-3 text-center p-6">
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
            Arrows / WASD to steer · Space to pause · endless wrap-around edges
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

        <p className="text-center text-xs text-gray-400 mt-8">
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
