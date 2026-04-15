import type { Phase } from "./lib/gameLogic";

export interface RoomStatePayload {
  phase: Phase;
  bpm: number;
  p1Pattern: number[] | null;
  failedAttempts: number;
  lastMatches: boolean[] | null;
  composerId: string;
  guesserId: string | null;
  roomCode: string;
  /** Rounds won per socket id (same keys as composer/guesser over time). */
  scores: Record<string, number>;
}
