import { segmentLabel, type Segment } from "../lib/constrainedGrid";

/** Read-only bar of segments (same look as the editor strip). */
export function SegmentRhythmStrip({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        minHeight: 48,
        alignItems: "stretch",
        flexWrap: "wrap",
      }}
    >
      {segments.map((s, i) => {
        const w = s.type === "rest" ? 1 : s.durationEighths;
        const label = segmentLabel(s);
        return (
          <div
            key={`${i}-${label}`}
            style={{
              flex: w,
              minWidth: 36,
              minHeight: 48,
              background: s.type === "rest" ? "#2a2838" : "#1e3d32",
              border: "1px solid #3d4a5c",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 11,
              padding: 4,
              textAlign: "center",
            }}
          >
            {label}
          </div>
        );
      })}
    </div>
  );
}
