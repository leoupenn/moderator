import type { RoomStatePayload } from "../types";

export function RoundScores({
  state,
  mySocketId,
}: {
  state: RoomStatePayload;
  mySocketId: string;
}) {
  const scores = state.scores ?? {};
  const mine = scores[mySocketId] ?? 0;
  const oppId =
    state.composerId === mySocketId ? state.guesserId : state.composerId;
  const theirs = oppId != null ? (scores[oppId] ?? 0) : null;

  return (
    <div
      style={{
        fontSize: 13,
        color: "#9aa0b4",
        marginBottom: "0.75rem",
        padding: "0.5rem 0.65rem",
        background: "#14141c",
        borderRadius: 8,
        border: "1px solid #2a2a36",
      }}
    >
      <strong style={{ color: "#c8cdd8" }}>Rounds won</strong>
      {" — "}
      You: <strong style={{ color: "#e8e6e3" }}>{mine}</strong>
      {theirs != null ? (
        <>
          {" · "}
          Opponent: <strong style={{ color: "#e8e6e3" }}>{theirs}</strong>
        </>
      ) : (
        <span className="muted"> · (waiting for opponent)</span>
      )}
    </div>
  );
}
