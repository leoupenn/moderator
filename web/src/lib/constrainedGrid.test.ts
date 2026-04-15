import { describe, expect, it } from "vitest";
import {
  decodeToSegments,
  encodeConstrainedPattern,
  noteNameForDuration,
  segmentLabel,
  type Segment,
} from "./constrainedGrid";
import { binaryPatternForPlayback, comparePatterns } from "./gameLogic";

describe("note names", () => {
  it("uses traditional names", () => {
    expect(noteNameForDuration(1)).toBe("Eighth note");
    expect(noteNameForDuration(2)).toBe("Quarter note");
    expect(noteNameForDuration(4)).toBe("Half note");
    expect(noteNameForDuration(8)).toBe("Whole note");
    expect(segmentLabel({ type: "rest" })).toBe("Eighth rest");
    expect(segmentLabel({ type: "note", durationEighths: 2 })).toBe("Quarter note");
  });
});

describe("constrained grid", () => {
  it("round-trips rest + eighth", () => {
    const segs: Segment[] = [
      { type: "note", durationEighths: 1 },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
    ];
    const p = encodeConstrainedPattern(segs);
    expect(decodeToSegments(p)).toEqual(segs);
  });

  it("round-trips quarter at start", () => {
    const segs: Segment[] = [
      { type: "note", durationEighths: 2 },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
      { type: "rest" },
    ];
    const p = encodeConstrainedPattern(segs);
    expect(p[0]).toBe(1);
    expect(p[3]).toBe(1);
    expect(decodeToSegments(p)).toEqual(segs);
  });

  it("self-compare full bar whole note", () => {
    const segs: Segment[] = [{ type: "note", durationEighths: 8 }];
    const p = binaryPatternForPlayback(encodeConstrainedPattern(segs));
    const { numCorrect } = comparePatterns(p, p);
    expect(numCorrect).toBe(16);
  });
});
