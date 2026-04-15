/** Parity with moderator/game_logic.py */

export const SLOTS = 16;
export const MAX_FAILED_ATTEMPTS = 5;
export const NEOPIXEL_FEEDBACK_COUNT = 8;

export const NEOPIXEL_REVERSE_STRIP = false;

function feedbackPhysicalIndices(): number[] {
  const r = Array.from({ length: NEOPIXEL_FEEDBACK_COUNT }, (_, i) => i);
  return NEOPIXEL_REVERSE_STRIP ? r.reverse() : r;
}

export const NEOPIXEL_PHYSICAL_INDICES: readonly number[] = feedbackPhysicalIndices();

export type Phase =
  | "P1_INPUT"
  | "P2_INPUT"
  | "FEEDBACK"
  | "ROUND_WON"
  | "ROUND_LOST_REVEAL";

export function slotRole(index: number): "start" | "end" {
  return index % 2 === 0 ? "start" : "end";
}

export function normalizePattern(raw: number[]): number[] {
  const head = raw.slice(0, SLOTS).map((x) => int(x));
  const pad = Math.max(0, SLOTS - head.length);
  return head.concat(Array(pad).fill(0));
}

function int(x: number): number {
  return Math.trunc(x);
}

export function binaryPatternForPlayback(raw: number[]): number[] {
  const p = normalizePattern(raw);
  return p.map((x) => (x ? 1 : 0));
}

export function comparePatterns(
  reference: number[],
  attempt: number[],
): { matches: boolean[]; numCorrect: number } {
  const a = normalizePattern(reference);
  const b = normalizePattern(attempt);
  const matches = a.map((v, i) => v === b[i]);
  const numCorrect = matches.filter(Boolean).length;
  return { matches, numCorrect };
}

export function feedbackLedChars(matches: boolean[]): string[] {
  return matches.map((m) => (m ? "G" : "R"));
}

export function neopixelRgbForFeedbackLed(
  matches: boolean[],
  ledIndex: number,
): [number, number, number] {
  if (matches.length !== SLOTS) {
    throw new Error("Need 16 match flags");
  }
  if (ledIndex < 0 || ledIndex >= NEOPIXEL_FEEDBACK_COUNT) {
    throw new Error("led_index must be 0..7");
  }
  const i0 = 2 * ledIndex;
  const i1 = i0 + 1;
  const ok = matches[i0] && matches[i1];
  return ok ? [0, 255, 0] : [255, 0, 0];
}

export function matchesToNeopixelRgb(
  matches: boolean[],
): [number, number, number][] {
  return Array.from({ length: NEOPIXEL_FEEDBACK_COUNT }, (_, k) =>
    neopixelRgbForFeedbackLed(matches, k),
  );
}

export function formatNeopixelFeedbackSerial(matches: boolean[]): string {
  if (NEOPIXEL_PHYSICAL_INDICES.length !== NEOPIXEL_FEEDBACK_COUNT) {
    throw new Error("NEOPIXEL_PHYSICAL_INDICES must have 8 entries");
  }
  const lines: string[] = ["C"];
  for (let ledIndex = 0; ledIndex < NEOPIXEL_FEEDBACK_COUNT; ledIndex++) {
    const [r, g, b] = neopixelRgbForFeedbackLed(matches, ledIndex);
    const phys = NEOPIXEL_PHYSICAL_INDICES[ledIndex];
    lines.push(`P ${phys} ${r} ${g} ${b}`);
  }
  lines.push("S");
  return `${lines.join("\n")}\n`;
}
