import { describe, expect, it } from "vitest";
import { isValidConstrainedPattern } from "../lib/constrainedGrid";
import { SOLO_PRESETS } from "./presets";

describe("SOLO_PRESETS", () => {
  it("every preset pattern is a valid constrained 8-slot bar", () => {
    for (const p of SOLO_PRESETS) {
      expect(isValidConstrainedPattern(p.pattern), p.id).toBe(true);
    }
  });
});
