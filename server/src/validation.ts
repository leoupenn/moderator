/** Duplicated from web/src/lib for server-side checks (keep in sync). */

export const SLOTS = 16;
export const MAX_FAILED_ATTEMPTS = 5;

export type Phase =
  | "P1_INPUT"
  | "P2_INPUT"
  | "FEEDBACK"
  | "ROUND_WON"
  | "ROUND_LOST_REVEAL";

function normalizePattern(raw: number[]): number[] {
  const head = raw.slice(0, SLOTS).map((x) => Math.trunc(x));
  const pad = Math.max(0, SLOTS - head.length);
  return head.concat(Array(pad).fill(0));
}

export function binaryPatternForPlayback(raw: number[]): number[] {
  return normalizePattern(raw).map((x) => (x ? 1 : 0));
}

export function comparePatterns(
  reference: number[],
  attempt: number[],
): { matches: boolean[]; numCorrect: number } {
  const a = normalizePattern(reference);
  const b = normalizePattern(attempt);
  const matches = a.map((v, i) => v === b[i]);
  return { matches, numCorrect: matches.filter(Boolean).length };
}

type NoteDuration = 1 | 2 | 4 | 8;
const ORDER: NoteDuration[] = [1, 2, 4, 8];

function validNoteAt(p: number[], k: number, d: number): boolean {
  if (k + d > 8) return false;
  const start = 2 * k;
  const end = 2 * (k + d) - 1;
  if (p[start] !== 1 || p[end] !== 1) return false;
  for (let i = start + 1; i < end; i++) {
    if (p[i] !== 0) return false;
  }
  return true;
}

export function isValidConstrainedPattern(pattern: number[]): boolean {
  const p = pattern.map((x) => (x ? 1 : 0));
  if (p.length !== 16) return false;
  let k = 0;
  while (k < 8) {
    if (p[2 * k] === 0 && p[2 * k + 1] === 0) {
      k += 1;
      continue;
    }
    let found: NoteDuration | null = null;
    for (const d of ORDER) {
      if (validNoteAt(p, k, d)) {
        found = d;
        break;
      }
    }
    if (!found) return false;
    k += found;
  }
  return true;
}

export function isBinaryPattern(raw: unknown): raw is number[] {
  if (!Array.isArray(raw) || raw.length !== SLOTS) return false;
  return raw.every((x) => x === 0 || x === 1);
}
