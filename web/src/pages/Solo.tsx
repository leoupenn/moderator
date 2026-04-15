import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LedRow } from "../components/LedRow";
import { SegmentEditor } from "../components/SegmentEditor";
import { SegmentRhythmStrip } from "../components/SegmentRhythmStrip";
import { SlotFeedback } from "../components/SlotFeedback";
import {
  encodeConstrainedPattern,
  type Segment,
} from "../lib/constrainedGrid";
import { comparePatterns, SLOTS } from "../lib/gameLogic";
import { getAudioContext, playPhraseOnly } from "../lib/audioPlayback";
import { loadPresetAudio, playSoloReference } from "../lib/soloReferenceAudio";
import { SOLO_PRESETS, type SoloPreset } from "../solo/presets";

const BESTS_KEY = "moderator-solo-bests";

type BestRecord = { attempts: number; timeMs: number };

function loadBests(): Record<string, BestRecord> {
  try {
    const raw = localStorage.getItem(BESTS_KEY);
    if (!raw) return {};
    const o = JSON.parse(raw) as Record<string, BestRecord>;
    return o && typeof o === "object" ? o : {};
  } catch {
    return {};
  }
}

function saveBestIfBetter(presetId: string, attempts: number, timeMs: number): void {
  const b = loadBests();
  const cur = b[presetId];
  if (
    !cur ||
    attempts < cur.attempts ||
    (attempts === cur.attempts && timeMs < cur.timeMs)
  ) {
    b[presetId] = { attempts, timeMs };
    localStorage.setItem(BESTS_KEY, JSON.stringify(b));
  }
}

function formatTimeMs(ms: number): string {
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(2)}s`;
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${m}m ${r.toFixed(1)}s`;
}

function sumEighths(segs: Segment[]): number {
  return segs.reduce((acc, s) => {
    if (s.type === "rest") return acc + 1;
    return acc + s.durationEighths;
  }, 0);
}

type RunPhase = "idle" | "feedback" | "won";

export function Solo() {
  const [bests, setBests] = useState<Record<string, BestRecord>>(() => loadBests());
  const [preset, setPreset] = useState<SoloPreset | null>(null);
  const [started, setStarted] = useState(false);
  const [startPerf, setStartPerf] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [localSegs, setLocalSegs] = useState<Segment[]>([]);
  const [runPhase, setRunPhase] = useState<RunPhase>("idle");
  const [lastMatches, setLastMatches] = useState<boolean[] | null>(null);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const audioBufferRef = useRef<AudioBuffer | null>(null);

  const lastSubmitRef = useRef<Segment[]>([]);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!started || startPerf == null || runPhase === "won") {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    const tick = () => {
      setElapsedMs(performance.now() - startPerf);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [started, startPerf, runPhase]);

  const patternFromSegs = useCallback(() => {
    if (sumEighths(localSegs) !== 8) return null;
    try {
      return encodeConstrainedPattern(localSegs);
    } catch {
      return null;
    }
  }, [localSegs]);

  const resetRun = useCallback(() => {
    setStarted(false);
    setStartPerf(null);
    setElapsedMs(0);
    setAttempts(0);
    setLocalSegs([]);
    setRunPhase("idle");
    setLastMatches(null);
    lastSubmitRef.current = [];
  }, []);

  const pickPreset = (p: SoloPreset) => {
    setPreset(p);
    resetRun();
    audioBufferRef.current = null;
    setAudioError(null);
    setBests(loadBests());
  };

  const playReference = async () => {
    if (!preset) return;
    const ctx = getAudioContext();
    await resumeCtx(ctx);
    setAudioLoading(true);
    setAudioError(null);
    try {
      const buf =
        audioBufferRef.current ??
        (await loadPresetAudio(ctx, preset.audioPath));
      audioBufferRef.current = buf;
      playSoloReference(ctx, buf, {
        bpm: preset.bpm,
        countIn: true,
        mixMetronomeDuringSample: preset.mixMetronomeDuringSample !== false,
      });
    } catch (e) {
      setAudioError(e instanceof Error ? e.message : "Audio load failed");
    } finally {
      setAudioLoading(false);
    }
  };

  const playMine = () => {
    if (!preset) return;
    const p = patternFromSegs();
    if (!p) return;
    void resumeCtx(getAudioContext()).then(() => {
      playPhraseOnly(p, preset.bpm);
    });
  };

  const submit = () => {
    if (!preset || !started || startPerf == null) return;
    const attempt = patternFromSegs();
    if (!attempt) return;
    lastSubmitRef.current = [...localSegs];
    const ref = preset.pattern;
    const { matches, numCorrect } = comparePatterns(ref, attempt);
    const nextAttempts = attempts + 1;
    setAttempts(nextAttempts);
    if (numCorrect === SLOTS) {
      const timeMs = performance.now() - startPerf;
      setElapsedMs(timeMs);
      saveBestIfBetter(preset.id, nextAttempts, timeMs);
      setBests(loadBests());
      setRunPhase("won");
      return;
    }
    setLastMatches(matches);
    setRunPhase("feedback");
  };

  const continueFeedback = () => {
    setLastMatches(null);
    setRunPhase("idle");
  };

  if (!preset) {
    return (
      <div style={{ padding: "1.25rem 1rem" }}>
        <div className="card">
          <p className="muted mb">
            <Link to="/">← Back</Link>
          </p>
          <h1>Singleplayer</h1>
          <p className="muted mb">
            Hear a preset clip, recreate the rhythm with blocks, and try for fewest attempts and
            best time. Reference uses a count-in and optional click track; “Play mine” is the sine
            preview only.
          </p>
          <h2 style={{ fontSize: "1rem", color: "#9aa0b4" }}>Presets</h2>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {SOLO_PRESETS.map((p) => {
              const b = bests[p.id];
              return (
                <li key={p.id} style={{ marginBottom: "0.65rem" }}>
                  <button type="button" onClick={() => pickPreset(p)}>
                    <strong>{p.title}</strong>
                    {b ? (
                      <span className="muted" style={{ marginLeft: 8 }}>
                        Best: {b.attempts} attempt{b.attempts === 1 ? "" : "s"} ·{" "}
                        {formatTimeMs(b.timeMs)}
                      </span>
                    ) : (
                      <span className="muted" style={{ marginLeft: 8 }}>
                        No best yet
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "1.25rem 1rem" }}>
      <div className="card">
        <p className="muted mb">
          <Link to="/">← Home</Link>
          {" · "}
          <button type="button" onClick={() => setPreset(null)}>
            All presets
          </button>
        </p>
        <h1>{preset.title}</h1>
        {preset.description ? <p className="muted mb">{preset.description}</p> : null}
        {bests[preset.id] ? (
          <p className="muted mb">
            Personal best: <strong>{bests[preset.id].attempts}</strong> attempt
            {bests[preset.id].attempts === 1 ? "" : "s"} ·{" "}
            <strong>{formatTimeMs(bests[preset.id].timeMs)}</strong>
          </p>
        ) : null}

        {runPhase === "won" ? (
          <div>
            <h2>Solved</h2>
            <p>
              Attempts: <strong>{attempts}</strong>
            </p>
            <p>
              Time: <strong>{formatTimeMs(elapsedMs)}</strong>
            </p>
            <div className="row mt">
              <button
                type="button"
                className="primary"
                onClick={() => {
                  resetRun();
                }}
              >
                Try again
              </button>
              <button type="button" onClick={() => setPreset(null)}>
                Pick another preset
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="row mb" style={{ alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              {!started ? (
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    setStarted(true);
                    setStartPerf(performance.now());
                    setElapsedMs(0);
                  }}
                >
                  Start challenge
                </button>
              ) : (
                <span style={{ color: "#9aa0b4" }}>
                  Time: <strong style={{ color: "#e8e6e3" }}>{formatTimeMs(elapsedMs)}</strong>
                  {" · "}
                  Attempts: <strong style={{ color: "#e8e6e3" }}>{attempts}</strong>
                </span>
              )}
            </div>

            {runPhase === "feedback" && lastMatches ? (
              <div className="mt">
                <h2>Feedback</h2>
                <h3 style={{ fontSize: "0.95rem", margin: "0 0 0.5rem", color: "#9aa0b4" }}>
                  Your submitted rhythm
                </h3>
                <SegmentRhythmStrip
                  segments={
                    lastSubmitRef.current.length > 0
                      ? lastSubmitRef.current
                      : localSegs
                  }
                />
                <div style={{ marginTop: "1rem" }} />
                <LedRow matches={lastMatches} />
                <SlotFeedback matches={lastMatches} />
                <button type="button" className="primary mt" onClick={continueFeedback}>
                  Continue
                </button>
              </div>
            ) : (
              <>
                <div className="row mb">
                  <button
                    type="button"
                    onClick={() => void playReference()}
                    disabled={audioLoading}
                  >
                    {audioLoading ? "Loading audio…" : "Play reference"}
                  </button>
                  <button
                    type="button"
                    onClick={() => playMine()}
                    disabled={!patternFromSegs()}
                  >
                    Play mine
                  </button>
                </div>
                {audioError ? <p style={{ color: "#f88" }}>{audioError}</p> : null}
                <LedRow matches={null} idle />
                <SegmentEditor
                  segments={localSegs}
                  onChange={setLocalSegs}
                  disabled={!started}
                />
                <div className="mt row">
                  <button
                    type="button"
                    className="primary"
                    disabled={!started || !patternFromSegs()}
                    onClick={submit}
                  >
                    Submit for grading
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

async function resumeCtx(ctx: AudioContext): Promise<void> {
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
}
