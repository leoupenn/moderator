import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSocket } from "../socket";
import type { RoomStatePayload } from "../types";

export function Home() {
  const nav = useNavigate();
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const s = getSocket();
    const onErr = (e: { message: string }) => setError(e.message);
    const onClosed = (e: { message?: string }) => {
      setError(e?.message ?? "Room closed.");
    };
    s.on("room:error", onErr);
    s.on("room:closed", onClosed);
    return () => {
      s.off("room:error", onErr);
      s.off("room:closed", onClosed);
    };
  }, []);

  const createRoom = () => {
    setError("");
    const s = getSocket();
    const onState = (st: RoomStatePayload) => {
      s.off("room:state", onState);
      nav(`/room/${st.roomCode}`);
    };
    s.once("room:state", onState);
    s.emit("create_room");
  };

  const joinRoom = () => {
    setError("");
    const c = joinCode.trim().toUpperCase();
    if (c.length < 4) {
      setError("Enter a room code.");
      return;
    }
    nav(`/room/${c}`);
  };

  return (
    <div style={{ padding: "2rem 1rem" }}>
      <div className="card">
        <h1>Moderator — digital rhythm</h1>
        <p className="muted mb">
          Two devices: one composer, one guesser. Create a room, share the code, then swap roles
          after each round.
        </p>
        <p className="muted mb" style={{ fontSize: 13 }}>
          <strong>Playing on two computers:</strong> run the server and Vite on one machine, then open{" "}
          <code style={{ wordBreak: "break-all" }}>{window.location.origin}</code> on <em>both</em>{" "}
          browsers (the guest must use the host&apos;s Wi‑Fi IP, not <code>localhost</code>).
        </p>
        {error ? (
          <p style={{ color: "#f88", marginBottom: "0.75rem" }}>{error}</p>
        ) : null}
        <div className="row mb">
          <button type="button" className="primary" onClick={createRoom}>
            Create room
          </button>
          <button type="button" onClick={() => nav("/solo")}>
            Singleplayer
          </button>
        </div>
        <h2>Join room</h2>
        <div className="row">
          <input
            type="text"
            style={{ width: "8rem", textTransform: "uppercase" }}
            placeholder="CODE"
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value)}
            maxLength={8}
          />
          <button type="button" onClick={joinRoom}>
            Join
          </button>
        </div>
      </div>
    </div>
  );
}
