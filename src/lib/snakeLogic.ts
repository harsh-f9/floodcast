// Pure Snake game logic — shared by the SnakeComingSoon page and the Node test.
// Keep this file free of React imports and use only erasable TypeScript
// (interfaces + type annotations) so Node 24 can import it directly.

export interface Pt {
  x: number;
  y: number;
}

export const PHRASE = "COMINGSOON";
export const PHRASE_LABEL = "COMING SOON";

export function letterForSegment(index: number): string {
  return PHRASE[index % PHRASE.length];
}

export function snakeLetters(length: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < length; i++) out.push(letterForSegment(i));
  return out;
}

export function wrap(v: number, max: number): number {
  return ((v % max) + max) % max;
}

export function createInitialSnake(): Pt[] {
  // Head-first: head C at (2,1), then O, then M tail — runs left→right across the top.
  return [
    { x: 2, y: 1 },
    { x: 1, y: 1 },
    { x: 0, y: 1 },
  ];
}

export function isOnSnake(cells: Pt[], p: Pt): boolean {
  for (const c of cells) {
    if (c.x === p.x && c.y === p.y) return true;
  }
  return false;
}

export function spawnApple(
  snake: Pt[],
  cols: number,
  rows: number,
  rand: () => number = Math.random
): Pt {
  const free: Pt[] = [];
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      if (!isOnSnake(snake, { x, y })) free.push({ x, y });
    }
  }
  if (free.length === 0) return { x: -1, y: -1 };
  const i = Math.floor(rand() * free.length);
  return free[i];
}

export interface StepResult {
  snake: Pt[];
  ate: boolean;
  died: boolean;
}

// Advance one tick. Toroidal (wrap-around) board: crossing any edge wraps.
export function stepSnake(
  snake: Pt[],
  dir: Pt,
  apple: Pt,
  cols: number,
  rows: number
): StepResult {
  const head = snake[0];
  const newHead: Pt = {
    x: wrap(head.x + dir.x, cols),
    y: wrap(head.y + dir.y, rows),
  };
  const ate = newHead.x === apple.x && newHead.y === apple.y;
  // If not growing, the tail vacates — exclude it from collision check.
  const bodyToCheck = ate ? snake : snake.slice(0, snake.length - 1);
  if (isOnSnake(bodyToCheck, newHead)) {
    return { snake, ate: false, died: true };
  }
  const next = [newHead, ...snake];
  if (!ate) next.pop();
  return { snake: next, ate, died: false };
}

export function isOpposite(a: Pt, b: Pt): boolean {
  return a.x === -b.x && a.y === -b.y;
}
