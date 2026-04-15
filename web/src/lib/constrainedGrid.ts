/**
 * 8 eighth-note columns tiling the bar; maps to 16-slot start/end pattern
 * (see plan: moderator digital rhythm).
 */

export type NoteDuration = 1 | 2 | 4 | 8;

export type Segment =
  | { type: "rest" }
  | { type: "note"; durationEighths: NoteDuration };

const ORDER: NoteDuration[] = [1, 2, 4, 8];

export function encodeConstrainedPattern(segments: Segment[]): number[] {
  let col = 0;
  const pattern = Array<number>(16).fill(0);
  for (const seg of segments) {
    if (seg.type === "rest") {
      col += 1;
      continue;
    }
    const d = seg.durationEighths;
    if (col + d > 8) {
      throw new Error("segments overflow 8 eighths");
    }
    pattern[2 * col] = 1;
    pattern[2 * (col + d) - 1] = 1;
    col += d;
  }
  if (col !== 8) {
    throw new Error("segments must cover exactly 8 eighths");
  }
  return pattern;
}

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

/** Decode 16-slot binary pattern to segments; null if not a valid constrained tiling. */
export function decodeToSegments(pattern: number[]): Segment[] | null {
  const p = pattern.map((x) => (x ? 1 : 0));
  if (p.length !== 16) return null;
  let k = 0;
  const out: Segment[] = [];
  while (k < 8) {
    if (p[2 * k] === 0 && p[2 * k + 1] === 0) {
      out.push({ type: "rest" });
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
    if (!found) return null;
    out.push({ type: "note", durationEighths: found });
    k += found;
  }
  return out;
}

export function isValidConstrainedPattern(pattern: number[]): boolean {
  return decodeToSegments(pattern) !== null;
}

/** Palette block ids for UI */
export const BLOCK_DURATIONS: NoteDuration[] = [1, 2, 4, 8];

export const EIGHTH_SLOTS = 8;

export function noteNameForDuration(d: NoteDuration): string {
  switch (d) {
    case 1:
      return "Eighth note";
    case 2:
      return "Quarter note";
    case 4:
      return "Half note";
    case 8:
      return "Whole note";
    default:
      return "Note";
  }
}

export function segmentLabel(seg: Segment): string {
  if (seg.type === "rest") return "Eighth rest";
  return noteNameForDuration(seg.durationEighths);
}
