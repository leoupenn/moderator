import { addClickAtTime } from "./metronome";

const CHANNELS = 2;

/** Decode URL to AudioBuffer (same sample rate as file). */
export async function loadPresetAudio(
  ctx: AudioContext,
  url: string,
): Promise<AudioBuffer> {
  if (!url) {
    return makeSilenceBuffer(ctx, 0.5);
  }
  const res = await fetch(url);
  if (!res.ok) {
    console.warn(`Solo audio fetch failed (${res.status}): ${url} — using silence.`);
    return makeSilenceBuffer(ctx, 0.5);
  }
  const arr = await res.arrayBuffer();
  return await ctx.decodeAudioData(arr.slice(0));
}

function makeSilenceBuffer(ctx: AudioContext, durationS: number): AudioBuffer {
  const sr = ctx.sampleRate;
  const frames = Math.max(1, Math.floor(durationS * sr));
  const buf = ctx.createBuffer(CHANNELS, frames, sr);
  return buf;
}

function interleaveFromAudioBuffer(buf: AudioBuffer): Float32Array {
  const ch = Math.min(CHANNELS, buf.numberOfChannels);
  const frames = buf.length;
  const out = new Float32Array(frames * CHANNELS);
  for (let i = 0; i < frames; i++) {
    for (let c = 0; c < CHANNELS; c++) {
      const s = c < ch ? buf.getChannelData(c)[i] : buf.getChannelData(0)[i];
      out[i * CHANNELS + c] = s;
    }
  }
  return out;
}

export interface PlaySoloReferenceOptions {
  bpm: number;
  /** Four quarter-note clicks before the sample starts. */
  countIn: boolean;
  /** Softer clicks on each quarter note for the duration of the sample (after count-in). */
  mixMetronomeDuringSample?: boolean;
  clickGain?: number;
}

/**
 * Renders sample + optional metronome to a buffer at the sample's rate, then plays via destination.
 */
export function playSoloReference(
  ctx: AudioContext,
  sample: AudioBuffer,
  opts: PlaySoloReferenceOptions,
): void {
  const sr = sample.sampleRate;
  const beatS = 60 / opts.bpm;
  const countInS = opts.countIn ? 4 * beatS : 0;
  const sampleFrames = sample.length;
  const countInFrames = Math.floor(countInS * sr);
  const totalFrames = countInFrames + sampleFrames;
  const interleaved = new Float32Array(totalFrames * CHANNELS);

  const sampleData = interleaveFromAudioBuffer(sample);
  interleaved.set(sampleData, countInFrames * CHANNELS);

  const clickGain = opts.clickGain ?? 0.28;
  if (opts.countIn) {
    for (let b = 0; b < 4; b++) {
      addClickAtTime(interleaved, CHANNELS, b * beatS, clickGain, sr);
    }
  }
  if (opts.mixMetronomeDuringSample) {
    const t0 = countInS;
    const dur = sample.duration;
    for (let t = 0; t < dur + 1e-6; t += beatS) {
      addClickAtTime(interleaved, CHANNELS, t0 + t, clickGain * 0.55, sr);
    }
  }

  const outBuf = ctx.createBuffer(CHANNELS, totalFrames, sr);
  for (let c = 0; c < CHANNELS; c++) {
    const ch = outBuf.getChannelData(c);
    for (let i = 0; i < totalFrames; i++) {
      ch[i] = interleaved[i * CHANNELS + c];
    }
  }
  const src = ctx.createBufferSource();
  src.buffer = outBuf;
  src.connect(ctx.destination);
  src.start();
}
