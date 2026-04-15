import { EIGHTH_SLOTS } from "../lib/constrainedGrid";

/**
 * One G/R cell per eighth-note slot (aggregates the two internal rhythm steps).
 */
export function SlotFeedback({ matches }: { matches: boolean[] }) {
  const chars = Array.from({ length: EIGHTH_SLOTS }, (_, k) => {
    const ok = matches[2 * k] && matches[2 * k + 1];
    return ok ? "G" : "R";
  });

  return (
    <div style={{ marginTop: 8 }}>
      <p className="muted" style={{ margin: "0 0 6px", fontSize: 12 }}>
        Per-slot match (8 slots)
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {chars.map((ch, i) => (
          <div key={i} style={{ textAlign: "center" }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 4,
                fontSize: 11,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: ch === "G" ? "#143214" : "#3d1515",
                color: ch === "G" ? "#6f6" : "#f88",
                border: "1px solid #333",
              }}
            >
              {ch}
            </div>
            <span
              style={{
                display: "block",
                fontSize: 9,
                color: "#7a8199",
                marginTop: 2,
              }}
            >
              {i + 1}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
