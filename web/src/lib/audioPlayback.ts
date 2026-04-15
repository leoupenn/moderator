import { renderHeldSinePhraseFloat32, stepDurationFromBpm } from "./phraseAudio";
import { binaryPatternForPlayback } from "./gameLogic";
import { mixReferencePlayback } from "./metronome";

const CHANNELS = 2;

let ctx: AudioContext | null = null;

export function getAudioContext(): AudioContext {
  if (!ctx) {
    ctx = new AudioContext({ sampleRate: 44100 });
  }
  return ctx;
}

async function resumeIfNeeded(audio: AudioContext): Promise<void> {
  if (audio.state === "suspended") {
    await audio.resume();
  }
}

export function playPhraseOnly(pattern: number[], bpm: number): void {
  const audio = getAudioContext();
  void resumeIfNeeded(audio).then(() => {
    const step = stepDurationFromBpm(bpm);
    const p = binaryPatternForPlayback(pattern);
    const data = renderHeldSinePhraseFloat32(p, step, { channels: CHANNELS });
    playBuffer(audio, data, CHANNELS);
  });
}

export function playReferenceWithMetronome(pattern: number[], bpm: number): void {
  const audio = getAudioContext();
  void resumeIfNeeded(audio).then(() => {
    const step = stepDurationFromBpm(bpm);
    const p = binaryPatternForPlayback(pattern);
    const phrase = renderHeldSinePhraseFloat32(p, step, { channels: CHANNELS });
    const mixed = mixReferencePlayback({
      bpm,
      phraseInterleaved: phrase,
      channels: CHANNELS,
    });
    playBuffer(audio, mixed, CHANNELS);
  });
}

function playBuffer(
  audio: AudioContext,
  interleaved: Float32Array,
  channels: number,
): void {
  const frames = interleaved.length / channels;
  const buffer = audio.createBuffer(channels, frames, 44100);
  for (let c = 0; c < channels; c++) {
    const ch = buffer.getChannelData(c);
    for (let i = 0; i < frames; i++) {
      ch[i] = interleaved[i * channels + c];
    }
  }
  const src = audio.createBufferSource();
  src.buffer = buffer;
  src.connect(audio.destination);
  src.start();
}
