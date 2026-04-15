import { SAMPLE_RATE } from "./phraseAudio";

const TWO_PI = Math.PI * 2;

/**
 * Short band-limited click (~2–3 ms) mixed into the buffer at `timeS`.
 */
export function addClickAtTime(
  interleaved: Float32Array,
  channels: number,
  timeS: number,
  gain: number,
  sampleRate: number = SAMPLE_RATE,
): void {
  const clickLen = Math.floor(sampleRate * 0.004);
  const startSample = Math.floor(timeS * sampleRate);
  for (let k = 0; k < clickLen; k++) {
    const n = startSample + k;
    if (n < 0 || n * channels >= interleaved.length) continue;
    const env = Math.sin((k / clickLen) * Math.PI);
    const tick = gain * env * Math.sin(TWO_PI * 1800 * (k / sampleRate));
    for (let c = 0; c < channels; c++) {
      const i = n * channels + c;
      interleaved[i] = Math.max(-1, Math.min(1, interleaved[i] + tick));
    }
  }
}

export interface MixReferenceOptions {
  bpm: number;
  phraseInterleaved: Float32Array;
  channels: number;
  /** Linear gain for clicks vs phrase (e.g. 0.35 ≈ −9 dB relative if phrase peaks ~1). */
  clickGain?: number;
}

/**
 * Count-in: 4 quarter-note clicks, then phrase buffer with 4 quarter clicks aligned to the bar.
 * Phrase is expected to start at t=0 in `phraseInterleaved`; output is longer by 4 beats.
 */
export function mixReferencePlayback(opts: MixReferenceOptions): Float32Array {
  const { bpm, phraseInterleaved, channels } = opts;
  const clickGain = opts.clickGain ?? 0.32;
  const beatS = 60 / bpm;
  const countInS = 4 * beatS;
  const phraseSamples = phraseInterleaved.length / channels;
  const countInSamples = Math.floor(countInS * SAMPLE_RATE);
  const totalSamples = countInSamples + phraseSamples;
  const out = new Float32Array(totalSamples * channels);
  out.set(phraseInterleaved, countInSamples * channels);

  for (let b = 0; b < 4; b++) {
    addClickAtTime(out, channels, b * beatS, clickGain);
  }
  const phraseStartS = countInSamples / SAMPLE_RATE;
  for (let b = 0; b < 4; b++) {
    addClickAtTime(out, channels, phraseStartS + b * beatS, clickGain * 0.85);
  }

  return out;
}

export function countInDurationS(bpm: number): number {
  return 4 * (60 / bpm);
}
