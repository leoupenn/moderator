/** Parity with moderator/phrase_audio.py */

import { SLOTS, normalizePattern } from "./gameLogic";

export const SAMPLE_RATE = 44100;
export const EDGE_RAMP_S = 0.004;
export const NOTE_GAP_MIN_S = 0.034;
export const NOTE_GAP_MAX_S = 0.072;
export const NOTE_GAP_FRACTION_OF_STEP = 0.52;

export function noteIntervalsFromPattern(pattern: number[]): [number, number][] {
  const p = normalizePattern(pattern);
  const queue: number[] = [];
  const intervals: [number, number][] = [];

  for (let i = 0; i < SLOTS; i++) {
    if (!p[i]) continue;
    if (i % 2 === 0) {
      queue.push(i);
    } else if (queue.length) {
      const s = queue.shift()!;
      intervals.push([s, i]);
    }
  }
  for (const s of queue) {
    intervals.push([s, SLOTS - 1]);
  }
  return intervals;
}

function noteAudioIntervalsS(
  pattern: number[],
  stepDurationS: number,
): [number, number][] {
  const d = stepDurationS;
  const noteIv = [...noteIntervalsFromPattern(pattern)].sort((a, b) => a[0] - b[0]);
  const gap = Math.min(
    NOTE_GAP_MAX_S,
    Math.max(NOTE_GAP_MIN_S, d * NOTE_GAP_FRACTION_OF_STEP),
  );
  const half = gap * 0.5;
  const out: [number, number][] = [];

  for (let i = 0; i < noteIv.length; i++) {
    const [s, e] = noteIv[i];
    let t0 = s * d;
    let t1 = (e + 1) * d;
    if (i > 0) {
      const [, ep] = noteIv[i - 1];
      if (s === ep + 1) t0 += half;
    }
    if (i < noteIv.length - 1) {
      const [sn] = noteIv[i + 1];
      if (sn === e + 1) t1 -= half;
    }
    if (t1 > t0 + 1e-9) out.push([t0, t1]);
  }
  return out;
}

function gateAt(t: number, audioIv: [number, number][]): boolean {
  return audioIv.some(([t0, t1]) => t0 <= t && t < t1);
}

/**
 * Renders one bar as Float32 interleaved stereo (L=R) for Web Audio.
 */
export function renderHeldSinePhraseFloat32(
  pattern: number[],
  stepDurationS: number,
  options?: { freqHz?: number; volume?: number; channels?: number },
): Float32Array {
  const freqHz = options?.freqHz ?? 440;
  const volume = options?.volume ?? 0.85;
  const channels = Math.max(1, options?.channels ?? 2);
  const T = SLOTS * stepDurationS;
  const numSamples = Math.max(1, Math.round(T * SAMPLE_RATE));
  const audioIv = noteAudioIntervalsS(pattern, stepDurationS);
  const rampN = Math.max(1, Math.round(SAMPLE_RATE * EDGE_RAMP_S));
  const slew = 1 / rampN;
  const tMax = stepDurationS * SLOTS;
  const out = new Float32Array(numSamples * channels);
  let gSmooth = 0;

  for (let n = 0; n < numSamples; n++) {
    const t = (n + 0.5) / SAMPLE_RATE;
    const tClamped = Math.min(t, tMax - 1e-9);
    const target = gateAt(tClamped, audioIv) ? 1 : 0;
    if (gSmooth < target) gSmooth = Math.min(target, gSmooth + slew);
    else if (gSmooth > target) gSmooth = Math.max(target, gSmooth - slew);

    const sample = volume * gSmooth * Math.sin(2 * Math.PI * freqHz * t);
    for (let c = 0; c < channels; c++) {
      out[n * channels + c] = Math.max(-1, Math.min(1, sample));
    }
  }
  return out;
}

export function stepDurationFromBpm(bpm: number): number {
  return 60 / bpm / 4;
}
