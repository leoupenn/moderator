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

const placeholderSegments: Segment[] = [
  { type: "note", durationEighths: 1 },
  { type: "rest" },
  { type: "rest" },
  { type: "rest" },
  { type: "rest" },
  { type: "rest" },
  { type: "rest" },
  { type: "rest" },
];

const PLACEHOLDER_PATTERN = encodeConstrainedPattern(placeholderSegments);

export const SOLO_PRESETS: SoloPreset[] = [
  {
    id: "placeholder",
    title: "Placeholder groove",
    description:
      "One eighth note then rests — swap audioPath and pattern when you add a real preset.",
    bpm: 88,
    pattern: PLACEHOLDER_PATTERN,
    audioPath: "",
    mixMetronomeDuringSample: true,
  },
];
