import {
  encodeConstrainedPattern,
  type Segment,
} from "../lib/constrainedGrid";

export type SoloPreset = {
  id: string;
  title: string;
  description?: string;
  bpm: number;
  /** 16-slot binary pattern; must pass isValidConstrainedPattern. */
  pattern: number[];
  /**
   * URL under public/, e.g. "/solo/myclip.wav".
   * Empty string = synthetic silence (no file) until you add a clip.
   */
  audioPath: string;
  /** Add quarter-note clicks over the sample after count-in. */
  mixMetronomeDuringSample?: boolean;
};

/** One bar: quarter, quarter, quarter, quarter rest (two eighth rests). */
const singleplayerBarSegments: Segment[] = [
  { type: "note", durationEighths: 2 },
  { type: "note", durationEighths: 2 },
  { type: "note", durationEighths: 2 },
  { type: "rest" },
  { type: "rest" },
];

const SINGLEPLAYER_PATTERN = encodeConstrainedPattern(singleplayerBarSegments);

export const SOLO_PRESETS: SoloPreset[] = [
  {
    id: "singleplayer",
    title: "Singleplayer",
    description:
      "Reference clip: WWRY.mp3. Tune bpm in presets.ts if the metronome drifts from your loop.",
    bpm: 81,
    pattern: SINGLEPLAYER_PATTERN,
    audioPath: "/solo/WWRY.mp3",
    mixMetronomeDuringSample: true,
  },
];
