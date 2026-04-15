import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import express from "express";
import cors from "cors";
import { Server } from "socket.io";
import {
  MAX_FAILED_ATTEMPTS,
  SLOTS,
  type Phase,
  binaryPatternForPlayback,
  comparePatterns,
  isBinaryPattern,
  isValidConstrainedPattern,
} from "./validation.js";

const PORT = Number(process.env.PORT) || 3847;

interface Room {
  code: string;
  composerId: string;
  guesserId: string | null;
  phase: Phase;
  bpm: number;
  p1Pattern: number[] | null;
  failedAttempts: number;
  lastMatches: boolean[] | null;
  /** Rounds won per socket id (guesser wins on perfect match; composer wins if guesser uses all attempts). */
  scores: Record<string, number>;
}

const rooms = new Map<string, Room>();

function ensureScore(room: Room, socketId: string): void {
  if (room.scores[socketId] === undefined) {
    room.scores[socketId] = 0;
  }
}

function bumpRoundWin(room: Room, socketId: string): void {
  ensureScore(room, socketId);
  room.scores[socketId] += 1;
}

function genCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let s = "";
  for (let i = 0; i < 6; i++) {
    s += chars[Math.floor(Math.random() * chars.length)];
  }
  if (rooms.has(s)) return genCode();
  return s;
}

function broadcastState(io: Server, room: Room) {
  const payload = {
    phase: room.phase,
    bpm: room.bpm,
    p1Pattern:
      room.phase === "P1_INPUT"
        ? null
        : room.p1Pattern
          ? [...room.p1Pattern]
          : null,
    failedAttempts: room.failedAttempts,
    lastMatches: room.lastMatches ? [...room.lastMatches] : null,
    composerId: room.composerId,
    guesserId: room.guesserId,
    roomCode: room.code,
    scores: { ...room.scores },
  };
  io.to(`room:${room.code}`).emit("room:state", payload);
}

function getRoomForSocket(socketId: string): Room | null {
  for (const r of rooms.values()) {
    if (r.composerId === socketId || r.guesserId === socketId) return r;
  }
  return null;
}

const app = express();
app.use(cors({ origin: true }));
app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

const __dirname = path.dirname(fileURLToPath(import.meta.url));
/** Built Vite app (repo root `web/dist`). Override with absolute `WEB_DIST`. */
const webDist = process.env.WEB_DIST
  ? path.resolve(process.env.WEB_DIST)
  : path.resolve(__dirname, "..", "..", "web", "dist");
const indexHtml = path.join(webDist, "index.html");

const httpServer = http.createServer(app);
const io = new Server(httpServer, {
  cors: { origin: true, methods: ["GET", "POST"] },
});

const serveUi =
  fs.existsSync(indexHtml) && process.env.SERVE_UI !== "0";

if (serveUi) {
  app.use(express.static(webDist));
  app.use((req, res, next) => {
    if (req.path.startsWith("/socket.io")) {
      next();
      return;
    }
    if (req.method !== "GET" && req.method !== "HEAD") {
      next();
      return;
    }
    res.sendFile(indexHtml, (err) => {
      if (err) next(err);
    });
  });
  console.log(`Serving web UI from ${webDist}`);
} else if (!fs.existsSync(indexHtml)) {
  console.warn(
    `Web UI not found (${indexHtml}). Build it: cd server && npm run build`,
  );
} else if (process.env.SERVE_UI === "0") {
  console.warn("SERVE_UI=0 — Socket.IO only (use Vite on :5173 for the UI in dev).");
}

io.on("connection", (socket) => {
  socket.on("create_room", () => {
    const code = genCode();
    const room: Room = {
      code,
      composerId: socket.id,
      guesserId: null,
      phase: "P1_INPUT",
      bpm: 80,
      p1Pattern: null,
      failedAttempts: 0,
      lastMatches: null,
      scores: { [socket.id]: 0 },
    };
    rooms.set(code, room);
    void socket.join(`room:${code}`);
    broadcastState(io, room);
  });

  socket.on("join_room", (code: string) => {
    if (typeof code !== "string") return;
    const c = code.trim().toUpperCase();
    const room = rooms.get(c);
    if (!room) {
      socket.emit("room:error", { message: "Room not found." });
      return;
    }
    if (room.composerId === socket.id) {
      ensureScore(room, socket.id);
      void socket.join(`room:${room.code}`);
      broadcastState(io, room);
      return;
    }
    if (room.guesserId && room.guesserId !== socket.id) {
      socket.emit("room:error", { message: "Room is full." });
      return;
    }
    room.guesserId = socket.id;
    ensureScore(room, room.composerId);
    ensureScore(room, socket.id);
    void socket.join(`room:${room.code}`);
    broadcastState(io, room);
  });

  socket.on("room:set_bpm", (bpm: number) => {
    const room = getRoomForSocket(socket.id);
    if (!room || room.composerId !== socket.id || room.phase !== "P1_INPUT") {
      return;
    }
    const v = Number(bpm);
    if (!Number.isFinite(v) || v < 20 || v > 300) return;
    room.bpm = v;
    broadcastState(io, room);
  });

  socket.on("room:p1_submit", (payload: { pattern: number[]; bpm: number }) => {
    const room = getRoomForSocket(socket.id);
    if (
      !room ||
      room.composerId !== socket.id ||
      room.phase !== "P1_INPUT" ||
      !room.guesserId
    ) {
      socket.emit("room:error", {
        message: "Cannot submit: you are not the composer or guesser is missing.",
      });
      return;
    }
    const { pattern, bpm } = payload ?? {};
    const bv = Number(bpm);
    if (!Number.isFinite(bv) || bv < 20 || bv > 300) {
      socket.emit("room:error", { message: "Invalid BPM." });
      return;
    }
    if (!isBinaryPattern(pattern) || !isValidConstrainedPattern(pattern)) {
      socket.emit("room:error", {
        message: "Invalid pattern (must be a valid 8-slot bar).",
      });
      return;
    }
    room.bpm = bv;
    room.p1Pattern = binaryPatternForPlayback(pattern);
    room.failedAttempts = 0;
    room.lastMatches = null;
    room.phase = "P2_INPUT";
    broadcastState(io, room);
  });

  socket.on("room:p2_submit", (payload: { pattern: number[] }) => {
    const room = getRoomForSocket(socket.id);
    if (
      !room ||
      room.guesserId !== socket.id ||
      room.phase !== "P2_INPUT" ||
      !room.p1Pattern
    ) {
      socket.emit("room:error", { message: "Cannot submit now." });
      return;
    }
    const pattern = payload?.pattern;
    if (!isBinaryPattern(pattern) || !isValidConstrainedPattern(pattern)) {
      socket.emit("room:error", {
        message: "Invalid pattern (must be a valid 8-slot bar).",
      });
      return;
    }
    const attempt = binaryPatternForPlayback(pattern);
    const { matches, numCorrect } = comparePatterns(room.p1Pattern, attempt);
    room.lastMatches = matches;

    if (numCorrect === SLOTS) {
      room.phase = "ROUND_WON";
      if (room.guesserId) bumpRoundWin(room, room.guesserId);
      broadcastState(io, room);
      return;
    }

    room.failedAttempts += 1;
    room.phase = "FEEDBACK";
    broadcastState(io, room);
  });

  socket.on("room:p2_continue", () => {
    const room = getRoomForSocket(socket.id);
    if (!room || room.guesserId !== socket.id || room.phase !== "FEEDBACK") {
      return;
    }
    if (room.failedAttempts >= MAX_FAILED_ATTEMPTS) {
      room.phase = "ROUND_LOST_REVEAL";
      bumpRoundWin(room, room.composerId);
      broadcastState(io, room);
      return;
    }
    room.phase = "P2_INPUT";
    room.lastMatches = null;
    broadcastState(io, room);
  });

  socket.on("room:new_round", () => {
    const room = getRoomForSocket(socket.id);
    if (
      !room ||
      (room.phase !== "ROUND_WON" && room.phase !== "ROUND_LOST_REVEAL")
    ) {
      return;
    }
    if (room.composerId !== socket.id && room.guesserId !== socket.id) {
      return;
    }
    if (!room.guesserId) return;
    const a = room.composerId;
    room.composerId = room.guesserId;
    room.guesserId = a;
    room.phase = "P1_INPUT";
    room.p1Pattern = null;
    room.failedAttempts = 0;
    room.lastMatches = null;
    broadcastState(io, room);
  });

  socket.on("disconnect", () => {
    for (const [code, room] of [...rooms.entries()]) {
      if (room.composerId !== socket.id && room.guesserId !== socket.id) {
        continue;
      }
      const partner =
        room.composerId === socket.id ? room.guesserId : room.composerId;
      rooms.delete(code);
      if (partner) {
        io.to(partner).emit("room:closed", {
          message: "The other player left the room.",
        });
      }
      break;
    }
  });
});

const HOST = process.env.HOST ?? "0.0.0.0";

httpServer.on("error", (err: NodeJS.ErrnoException) => {
  if (err.code === "EADDRINUSE") {
    console.error(
      `Port ${PORT} is already in use (another server or app is listening).\n` +
        `  • Use another port:  PORT=3947 npm start\n` +
        `  • Or free this port:    lsof -nP -iTCP:${PORT} -sTCP:LISTEN   then kill the PID shown.`,
    );
    process.exit(1);
  }
  throw err;
});

httpServer.listen(PORT, HOST, () => {
  const hostLabel = HOST === "0.0.0.0" ? "0.0.0.0 (all interfaces)" : HOST;
  console.log(`Game server + Socket.IO listening on ${hostLabel}:${PORT}`);
  if (serveUi) {
    console.log(`Open the game in a browser at http://127.0.0.1:${PORT} (or your LAN IP + this port).`);
  } else {
    console.log(
      "Socket.IO only (no static UI). For LAN dev with Vite, use port 5173 on this machine.",
    );
  }
});
