import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LedRow } from "../components/LedRow";
import { RoundScores } from "../components/RoundScores";
import { SegmentEditor } from "../components/SegmentEditor";
import { SegmentRhythmStrip } from "../components/SegmentRhythmStrip";
import { SlotFeedback } from "../components/SlotFeedback";
import {
  decodeToSegments,
  encodeConstrainedPattern,
  type Segment,
} from "../lib/constrainedGrid";
import { MAX_FAILED_ATTEMPTS } from "../lib/gameLogic";
import {
  playPhraseOnly,
  playReferenceWithMetronome,
} from "../lib/audioPlayback";
import { getSocket } from "../socket";
import type { RoomStatePayload } from "../types";

function sumEighths(segs: Segment[]): number {
  return segs.reduce((acc, s) => {
    if (s.type === "rest") return acc + 1;
    return acc + s.durationEighths;
  }, 0);
}

export function Room() {
  const { code } = useParams<{ code: string }>();
  const nav = useNavigate();
  const [state, setState] = useState<RoomStatePayload | null>(null);
  const [socketId, setSocketId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [localSegs, setLocalSegs] = useState<Segment[]>([]);
  const [bpmLocal, setBpmLocal] = useState(80);

  const prevPhase = useRef<string | null>(null);
  const bpmDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Snapshot of guesser segments at last “Submit for grading” (for feedback screen). */
  const lastSubmittedAttemptRef = useRef<Segment[]>([]);

  useEffect(() => {
    const s = getSocket();
    const onConnect = () => setSocketId(s.id ?? null);
    const onState = (st: RoomStatePayload) => {
      setState(st);
      setBpmLocal(st.bpm);
    };
    const onErr = (e: { message: string }) => setError(e.message);
    const onClosed = () => {
      nav("/");
    };
    if (s.connected) setSocketId(s.id ?? null);
    s.on("connect", onConnect);
    s.on("room:state", onState);
    s.on("room:error", onErr);
    s.on("room:closed", onClosed);
    return () => {
      s.off("connect", onConnect);
      s.off("room:state", onState);
      s.off("room:error", onErr);
      s.off("room:closed", onClosed);
    };
  }, [nav]);

  useEffect(() => {
    if (!code) return;
    getSocket().emit("join_room", code);
  }, [code]);

  useEffect(() => {
    if (!state || !socketId) return;
    const isComposer = state.composerId === socketId;
    const isGuesser = state.guesserId === socketId;
    const p = state.phase;
    if (p === "P1_INPUT" && isComposer && prevPhase.current !== "P1_INPUT") {
      setLocalSegs([]);
    }
    if (p === "P2_INPUT" && isGuesser && prevPhase.current !== "P2_INPUT") {
      setLocalSegs([]);
    }
    prevPhase.current = p;
  }, [state, socketId]);

  const isComposer = state && socketId && state.composerId === socketId;
  const isGuesser = state && socketId && state.guesserId === socketId;

  const patternFromSegs = useCallback(() => {
    if (sumEighths(localSegs) !== 8) return null;
    try {
      return encodeConstrainedPattern(localSegs);
    } catch {
      return null;
    }
  }, [localSegs]);

  const scheduleBpmEmit = useCallback((v: number) => {
    if (bpmDebounce.current) clearTimeout(bpmDebounce.current);
    bpmDebounce.current = setTimeout(() => {
      getSocket().emit("room:set_bpm", v);
    }, 200);
  }, []);

  if (!code) {
    return null;
  }

  if (!state || !socketId) {
    return (
      <div style={{ padding: "2rem" }} className="muted">
        Connecting…
      </div>
    );
  }

  const st = state;

  const composerViewP1 =
    isComposer && st.phase === "P1_INPUT" ? (
      <div>
        <h2>Composer — build a rhythm</h2>
        <p className="muted mb">
          Room <strong>{st.roomCode}</strong>. Share this code with your partner. Waiting for
          guesser: {st.guesserId ? "joined" : "not yet"}.
        </p>
        <div className="row mb">
          <label>
            BPM{" "}
            <input
              type="number"
              min={20}
              max={300}
              value={bpmLocal}
              onChange={(e) => {
                const v = Number(e.target.value);
                setBpmLocal(v);
                scheduleBpmEmit(v);
              }}
            />
          </label>
        </div>
        <LedRow matches={null} idle />
        <SegmentEditor
          segments={localSegs}
          onChange={setLocalSegs}
          disabled={!st.guesserId}
        />
        <div className="mt row">
          <button
            type="button"
            className="primary"
            disabled={!st.guesserId || !patternFromSegs()}
            onClick={() => {
              const p = patternFromSegs();
              if (!p) return;
              getSocket().emit("room:p1_submit", { pattern: p, bpm: bpmLocal });
            }}
          >
            Submit rhythm (lock for guesser)
          </button>
        </div>
      </div>
    ) : null;

  const composerWaiting =
    isComposer && (st.phase === "P2_INPUT" || st.phase === "FEEDBACK") ? (
      <div>
        <h2>Composer</h2>
        <p className="muted">
          Phase: <strong>{st.phase}</strong>. Your partner is on the guesser screen.
        </p>
      </div>
    ) : null;

  const guesserView =
    isGuesser && st.phase === "P2_INPUT" ? (
      <div>
        <h2>Guesser — match the rhythm</h2>
        <p className="muted mb">
          Reference uses a 4-beat count-in and a click track. “Play mine” is phrase only.
          Attempts: {st.failedAttempts} / {MAX_FAILED_ATTEMPTS}.
        </p>
        <div className="row mb">
          <button
            type="button"
            onClick={() => {
              if (st.p1Pattern) playReferenceWithMetronome(st.p1Pattern, st.bpm);
            }}
            disabled={!st.p1Pattern}
          >
            Play reference (count-in + clicks)
          </button>
          <button
            type="button"
            onClick={() => {
              const p = patternFromSegs();
              if (p) playPhraseOnly(p, st.bpm);
            }}
            disabled={!patternFromSegs()}
          >
            Play mine
          </button>
        </div>
        <LedRow matches={null} idle />
        <SegmentEditor segments={localSegs} onChange={setLocalSegs} />
        <div className="mt row">
          <button
            type="button"
            className="primary"
            disabled={!patternFromSegs()}
            onClick={() => {
              const p = patternFromSegs();
              if (!p) return;
              lastSubmittedAttemptRef.current = [...localSegs];
              getSocket().emit("room:p2_submit", { pattern: p });
            }}
          >
            Submit for grading
          </button>
        </div>
      </div>
    ) : null;

  const feedbackView =
    isGuesser && st.phase === "FEEDBACK" && st.lastMatches ? (
      <div>
        <h2>Feedback</h2>
        <p className="muted mb">
          Eight slots: each LED and letter is green only if your rhythm matches the composer for
          that beat (slot 1 = first eighth, … slot 8 = last eighth).
        </p>
        <h3 style={{ fontSize: "0.95rem", margin: "0 0 0.5rem", color: "#9aa0b4" }}>
          Your submitted rhythm
        </h3>
        <SegmentRhythmStrip
          segments={
            lastSubmittedAttemptRef.current.length > 0
              ? lastSubmittedAttemptRef.current
              : localSegs
          }
        />
        <div style={{ marginTop: "1rem" }} />
        <LedRow matches={st.lastMatches} />
        <SlotFeedback matches={st.lastMatches} />
        <button
          type="button"
          className="primary mt"
          onClick={() => getSocket().emit("room:p2_continue")}
        >
          Continue
        </button>
      </div>
    ) : null;

  const wonView =
    isGuesser && st.phase === "ROUND_WON" ? (
      <div>
        <h2>Round won</h2>
        <p className="muted">You matched all 8 slots.</p>
        <button type="button" className="primary mt" onClick={() => getSocket().emit("room:new_round")}>
          New round (swap roles)
        </button>
      </div>
    ) : null;

  const lostView =
    isGuesser && st.phase === "ROUND_LOST_REVEAL" ? (
      <div>
        <h2>Reveal — out of attempts</h2>
        <p className="muted mb">Composer rhythm (8 slots):</p>
        {st.p1Pattern ? (
          <SegmentRhythmStrip segments={decodeToSegments(st.p1Pattern) ?? []} />
        ) : null}
        <button type="button" className="primary mt" onClick={() => getSocket().emit("room:new_round")}>
          New round (swap roles)
        </button>
      </div>
    ) : null;

  const guesserIdle =
    isGuesser && st.phase === "P1_INPUT" ? (
      <div>
        <h2>Guesser</h2>
        <p className="muted">Waiting for the composer to finish and submit…</p>
      </div>
    ) : null;

  const notInRoom =
    socketId &&
    st.composerId !== socketId &&
    st.guesserId !== socketId ? (
      <p className="muted">You are not in this room. Check the code.</p>
    ) : null;

  return (
    <div style={{ padding: "1.25rem 1rem" }}>
      <div className="card">
        <RoundScores state={st} mySocketId={socketId} />
        {error ? <p style={{ color: "#f88" }}>{error}</p> : null}
        {notInRoom}
        {composerViewP1}
        {composerWaiting}
        {guesserIdle}
        {guesserView}
        {feedbackView}
        {wonView}
        {lostView}
        {isComposer && st.phase === "ROUND_LOST_REVEAL" ? (
          <div className="mt">
            <h2>Reveal</h2>
            <p className="muted mb">Your pattern is shown on the guesser device.</p>
            <button type="button" className="primary" onClick={() => getSocket().emit("room:new_round")}>
              New round (swap roles)
            </button>
          </div>
        ) : null}
        {isComposer && st.phase === "ROUND_WON" ? (
          <div className="mt">
            <p className="muted">Guesser matched. Swap roles for the next round.</p>
            <button type="button" className="primary" onClick={() => getSocket().emit("room:new_round")}>
              New round (swap roles)
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
