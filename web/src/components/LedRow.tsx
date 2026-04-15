import { matchesToNeopixelRgb } from "../lib/gameLogic";

interface LedRowProps {
  matches: boolean[] | null;
  idle?: boolean;
}

export function LedRow({ matches, idle }: LedRowProps) {
  const colors =
    matches && !idle
      ? matchesToNeopixelRgb(matches)
      : Array.from({ length: 8 }, () => [0x44, 0x44, 0x55] as [number, number, number]);

  return (
    <div className="led-row" style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", gap: 8 }}>
        {colors.map(([r, g, b], i) => (
          <div
            key={i}
            title={`Slot ${i + 1}`}
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: `rgb(${r},${g},${b})`,
              boxShadow:
                matches && !idle
                  ? `0 0 12px rgba(${r},${g},${b},0.65)`
                  : "inset 0 0 6px rgba(0,0,0,0.4)",
              border: "1px solid #222",
            }}
          />
        ))}
      </div>
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 4,
          fontSize: 10,
          color: "#7a8199",
        }}
      >
        {colors.map((_, i) => (
          <span key={i} style={{ width: 28, textAlign: "center" }}>
            {i + 1}
          </span>
        ))}
      </div>
    </div>
  );
}
