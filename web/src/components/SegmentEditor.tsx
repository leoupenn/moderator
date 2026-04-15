import {
  BLOCK_DURATIONS,
  noteNameForDuration,
  segmentLabel,
  type Segment,
} from "../lib/constrainedGrid";

function sumEighths(segs: Segment[]): number {
  return segs.reduce((acc, s) => {
    if (s.type === "rest") return acc + 1;
    return acc + s.durationEighths;
  }, 0);
}

interface SegmentEditorProps {
  segments: Segment[];
  onChange: (next: Segment[]) => void;
  disabled?: boolean;
}

export function SegmentEditor({
  segments,
  onChange,
  disabled,
}: SegmentEditorProps) {
  const remaining = 8 - sumEighths(segments);
  const complete = remaining === 0;

  const add = (seg: Segment) => {
    const need = seg.type === "rest" ? 1 : seg.durationEighths;
    if (need > remaining) return;
    onChange([...segments, seg]);
  };

  const undo = () => {
    if (segments.length === 0) return;
    onChange(segments.slice(0, -1));
  };

  const clear = () => onChange([]);

  return (
    <div>
      <div className="row mb" style={{ flexWrap: "wrap" }}>
        <button
          type="button"
          disabled={disabled || remaining < 1}
          onClick={() => add({ type: "rest" })}
        >
          + Eighth rest
        </button>
        {BLOCK_DURATIONS.map((d) => (
          <button
            key={d}
            type="button"
            disabled={disabled || remaining < d}
            onClick={() => add({ type: "note", durationEighths: d })}
          >
            + {noteNameForDuration(d)}
          </button>
        ))}
        <button type="button" disabled={disabled || segments.length === 0} onClick={undo}>
          Undo
        </button>
        <button type="button" disabled={disabled || segments.length === 0} onClick={clear}>
          Clear
        </button>
      </div>
      <p className="muted">
        {complete
          ? "Bar complete — ready to submit."
          : `Fill all 8 slots: ${remaining} eighth beat(s) left.`}
      </p>
      <div
        style={{
          display: "flex",
          gap: 4,
          minHeight: 56,
          alignItems: "stretch",
          flexWrap: "wrap",
        }}
      >
        {segments.map((s, i) => {
          const w =
            s.type === "rest" ? 1 : s.durationEighths;
          const flex = w;
          const label = segmentLabel(s);
          return (
            <div
              key={`${i}-${label}`}
              style={{
                flex: flex,
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
              }}
            >
              {label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
