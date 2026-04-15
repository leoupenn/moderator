import { describe, expect, it } from "vitest";
import {
  comparePatterns,
  matchesToNeopixelRgb,
  normalizePattern,
  SLOTS,
} from "./gameLogic";

describe("comparePatterns", () => {
  it("matches identical patterns", () => {
    const p = Array(SLOTS).fill(0);
    p[0] = 1;
    p[1] = 1;
    const { matches, numCorrect } = comparePatterns(p, p);
    expect(numCorrect).toBe(SLOTS);
    expect(matches.every(Boolean)).toBe(true);
  });

  it("flags mismatches per slot", () => {
    const a = Array(SLOTS).fill(0);
    const b = Array(SLOTS).fill(0);
    a[0] = 1;
    b[0] = 0;
    const { matches, numCorrect } = comparePatterns(a, b);
    expect(numCorrect).toBe(SLOTS - 1);
    expect(matches[0]).toBe(false);
  });
});

describe("LED mapping", () => {
  it("green only when both slots in pair match", () => {
    const matches = Array(SLOTS).fill(true);
    matches[0] = false;
    const rgb = matchesToNeopixelRgb(matches);
    expect(rgb[0]).toEqual([255, 0, 0]);
    expect(rgb[1]).toEqual([0, 255, 0]);
  });
});

describe("normalizePattern", () => {
  it("pads and truncates to 16", () => {
    expect(normalizePattern([1]).length).toBe(SLOTS);
    expect(normalizePattern(Array(20).fill(1)).length).toBe(SLOTS);
  });
});
