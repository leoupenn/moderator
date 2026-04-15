# Moderator

Desktop host for a two-player, turn-based rhythm duel: **Player 1** sets a 16-step pattern on a capacitive controller; **Player 2** hears it and tries to match. The app is **PySide6**; the controller is **XIAO ESP32-C3** firmware with dual **MPR121** sensors and an 8-LED **NeoPixel** strip for grading feedback.

## Digital web app (rooms)

A browser version lives under [`web/`](web/) (Vite + React + TypeScript) with a small Socket.IO server in [`server/`](server/). Two devices join the same room code: one **composer** fills **8 slots** (one bar of eighth beats) using **eighth rest**, **eighth note**, **quarter note**, **half note**, and **whole note** blocks; the other **guesser** hears **Play reference** with a **4-beat metronome count-in** and **quarter-note clicks** under the phrase, rebuilds the rhythm, and submits for grading. **Grading** matches [`moderator/game_logic.py`](moderator/game_logic.py) internally (16 start/end steps); the UI shows **8 slot** LEDs and G/R letters (green only if that eighth matches). Phrase audio follows [`moderator/phrase_audio.py`](moderator/phrase_audio.py) (FIFO start/end, gaps, sine). **Play mine** is phrase audio only (no count-in or clicks).

### Singleplayer (preset rhythms)

Route **`/solo`** (also **Singleplayer** on the home page): client-only practice. Presets are defined in [`web/src/solo/presets.ts`](web/src/solo/presets.ts); each has a **BPM**, a **constrained 16-step pattern** (for grading), and an optional **`audioPath`** under [`web/public/solo/`](web/public/solo/) for a **reference clip** (decoded in the browser). **Start challenge** begins the timer; each **Submit for grading** counts as an attempt until you match. Best **attempt count** (then fastest time) per preset is stored in **`localStorage`**.

**You are responsible for licensing** any commercial audio you add under `public/solo/`. The default preset uses **`public/solo/WWRY.mp3`**; set **`bpm`** and **`pattern`** in `presets.ts` to match your loop.

**Run locally (one machine)**

1. Terminal A: `cd server && npm install && npm run dev` — listens on **0.0.0.0:3847** (override with `PORT` / `HOST`).
2. Terminal B: `cd web && npm install && npm run dev` — Vite listens on **all interfaces** (e.g. **5173**). Open `http://127.0.0.1:5173` or `http://localhost:5173`.

**Two computers on the same Wi‑Fi (LAN)**

`127.0.0.1` only ever means “this same device,” so a second laptop cannot use it to reach your server.

1. On the machine that runs the game host, start **server** and **web** as above.
2. Find a working LAN address: from `web/` run **`npm run lan-ip`** (prints `http://…:5173` per interface). Or macOS: `ipconfig getifaddr en0` (Wi‑Fi is often `en0`). If several IPs appear, try each until the guest browser loads the page.
3. On **both** computers, use the **same** page URL (e.g. `http://192.168.1.23:5173`). Do **not** open `localhost` on the guest machine.
4. On the **host** PC, allow **inbound** TCP **5173** in the firewall (Vite). In dev, Socket.IO is proxied through that port, so guests do **not** need to reach **3847** unless you point `VITE_SOCKET_URL` at `:3847` directly.
5. In dev, use only a URL like `http://192.168.x.x:5173` on every device; the app connects to Socket.IO via the same origin and Vite forwards to the server on the host.

**LAN without Vite (one port)**  
After `cd server && npm run build`, run `npm start` and open `http://<host-LAN-IP>:3847` on every device (UI + Socket.IO together). If you still use `npm run dev` in `server/` while a `web/dist` exists and you do **not** want the server to serve that build, set **`SERVE_UI=0`** so only Socket.IO listens on `3847` and you keep using Vite on `5173`.

For production (static files + API elsewhere), build the web app with `VITE_SOCKET_URL` set to the public `https://…` origin of your Socket.IO server.

### Hosting so internet multiplayer works

You need **(1)** the React app somewhere players can open it, and **(2)** the **Socket.IO** server reachable from their browsers (HTTPS → `wss://` is normal in production).

**Recommended: one public URL (simplest)**  
The game server can serve **both** the built React app and Socket.IO on **one port** (see [`server/src/index.ts`](server/src/index.ts): `express.static` for [`web/dist`](web/dist), then SPA fallback; Socket.IO stays on the same HTTP server).

1. **Install once** (from repo root): `cd web && npm install` and `cd server && npm install`.
2. **Build** from `server/`: `npm run build` — this runs the Vite production build, then compiles the server. It expects the repo layout `moderator/web/dist` next to `moderator/server/dist`.
3. **Run**: `cd server && npm start` (or `node dist/index.js`). Default port **`3847`**; override with `PORT` (many hosts set `PORT` for you).
4. **Open** `http://127.0.0.1:3847` locally, or `http://<your-LAN-IP>:3847` for another device on the same Wi‑Fi (no Vite required for this mode).
5. **Internet / HTTPS**: Put **Caddy** or **nginx** in front: terminate TLS on **443**, **reverse-proxy** everything to `http://127.0.0.1:3847` (or whatever port Node uses). Players use only `https://your-domain.com`.  
   Do **not** set `VITE_SOCKET_URL` for this layout — the client already uses `window.location.origin` in production builds.

Optional: set **`WEB_DIST`** to an absolute path if you deploy the built `web/dist` somewhere other than the default relative location.

**Reverse proxy only (advanced)**  
If you prefer nginx to serve static files and only proxy `/socket.io` to Node, you can — but then you must build the web app with `VITE_SOCKET_URL` pointing at the public API origin, or serve JS that knows the socket host. The built-in static server avoids that.

**Alternative: split static + API**  
Example: UI on **Cloudflare Pages** / **Netlify**, game server on **Fly.io** / **Railway** / **Render**. Browsers will block or confuse wrong origins unless you set at **build** time:

```bash
cd web && VITE_SOCKET_URL=https://your-socket-host.fly.dev npm run build
```

Use the **exact** public `https://…` (or `http://…`) origin where Socket.IO listens. Keep server **CORS** permissive (already `origin: true`) for this pattern.

**Checklist**

- **TLS**: Use HTTPS in production; Socket.IO will use WebSockets (`wss`) automatically.
- **Process**: Server must stay running (`node`, `pm2`, Docker, or the platform’s “always on” web service).
- **Firewall / platform**: Allow inbound traffic on the port your process uses (often `443` behind a reverse proxy, not raw `3847` on the public internet).
- **Same session**: Scores and rooms live **in server memory**; restarting the process clears them. For durability you’d add Redis or a DB later.

**Rules parity**: [`web/src/lib/gameLogic.ts`](web/src/lib/gameLogic.ts) mirrors `game_logic.py`; [`web/src/lib/phraseAudio.ts`](web/src/lib/phraseAudio.ts) mirrors `phrase_audio.py`. The server repeats constrained-pattern checks in [`server/src/validation.ts`](server/src/validation.ts) (keep in sync with [`web/src/lib/constrainedGrid.ts`](web/src/lib/constrainedGrid.ts)).

**Honest play**: After the composer submits, the reference pattern is present in room state so the guesser’s browser can synthesize audio. Treat this as a trusted, in-person game; cheating via devtools is possible without a server-rendered audio-only stream.

**Scoring**: The server keeps **rounds won** per connection (shown at the top of the room). The **guesser** earns a round when they submit a perfect match; the **composer** earns a round when the guesser runs out of attempts without matching. Totals carry over when you swap roles; leaving the room clears the session.

**Tests**: `cd web && npm test`

---

The section below is a **prototype iteration log** from build sessions (not a full architecture guide). Entries are chronological; later steps sometimes supersede earlier ones. This repo has **no git history** — each “link” is a **relative path and line range** in the tree.

---

## Major vs minor

- **Major**: User-visible behavior, host↔device protocol, concurrency/threading, or fixes that unblock hardware.
- **Minor**: Refactors, mapping/tuning toggles, UI copy, or small hardening without changing the overall design.

---

## Current serial protocol (host → device)

Documented in the firmware header: [`firmware/note_detector/note_detector.ino`](firmware/note_detector/note_detector.ino) (lines 1–12). The recommended frame is **`C`**, then eight **`P <phys> r g b`** lines, then **`S`**. The Python helper that builds it is [`format_neopixel_feedback_serial`](moderator/game_logic.py) in [`moderator/game_logic.py`](moderator/game_logic.py) (lines 85–100).

---

## Iteration log

### 1 — NeoPixel grading feedback — **Major**

After P2 submits, imperfect matches drive **eight** LEDs: each LED reflects one **pair** of rhythm slots (start/end); both must match P1 for green, else red. The UI still shows 16 per-slot G/R cells.

**Code today**

- Rules and RGB per pair: [`compare_patterns`](moderator/game_logic.py) (lines 47–55), [`neopixel_rgb_for_feedback_led`](moderator/game_logic.py) (lines 63–76), [`matches_to_neopixel_rgb`](moderator/game_logic.py) (lines 78–82).
- UI + trigger: [`_apply_feedback_cells`](moderator/main_window.py) (lines 464–476), [`_p2_submit_grade`](moderator/main_window.py) (lines 545–570).
- Device RX: [`readLEDCommand`](firmware/note_detector/note_detector.ino) (lines 194–219) dispatching `M` / `C` / `S` / `P` / legacy lines.

---

### 2 — Perfect round and clear-strip helpers — **Minor**

Send all-green on a perfect match; clear the strip when starting a **new round** (helpers evolved when the wire format moved from `M` batch to `C`/`P`/`S`).

**Code today**

- [`format_neopixel_all_green_serial`](moderator/game_logic.py) (lines 103–109), [`format_neopixel_clear_serial`](moderator/game_logic.py) (lines 112–113).
- Perfect match: [`_p2_submit_grade`](moderator/main_window.py) (lines 558–564).
- Clear on new round: [`_new_round`](moderator/main_window.py) (lines 583–595).

---

### 3 — Thread-safe serial writes — **Major**

Queued Qt slots on the reader thread never ran because `run()` is a blocking loop without an event loop. Outbound lines are pushed through a **thread-safe queue** drained inside `run()`.

**Code today**

- [`SerialReaderWorker.enqueue_line`](moderator/serial_reader.py) (lines 27–29), [`_flush_writes`](moderator/serial_reader.py) (lines 40–55), [`run`](moderator/serial_reader.py) (lines 57–78).
- [`send_m_line`](moderator/receiver.py) (lines 13–25), [`send_led`](moderator/receiver.py) (lines 28–30).
- UI bridge: [`_send_m_line`](moderator/main_window.py) (lines 495–496).

---

### 4 — Shared per-feedback-index path — **Minor**

One Python function computes RGB for feedback index `k`; firmware uses one mapper for all eight indices so LED 0 and LED 7 share the same code path.

**Code today**

- [`neopixel_rgb_for_feedback_led`](moderator/game_logic.py) (lines 63–76); [`format_neopixel_feedback_serial`](moderator/game_logic.py) (lines 94–99) calls it per index.
- [`setMappedFeedbackPixel`](firmware/note_detector/note_detector.ino) (lines 92–99); [`applyMLine`](firmware/note_detector/note_detector.ino) (lines 101–110) uses it for `M` batches.

---

### 5 — Strict `M`-line parsing (firmware) — **Major**

Incomplete `M …` lines (e.g. early newline) used to parse the first RGB triple correctly while leaving the parser stuck so LEDs 1–7 appeared off. The sketch now requires **exactly 24** integers after `M` or it skips the update.

**Code today**

- [`parseMLine24`](firmware/note_detector/note_detector.ino) (lines 68–90), [`applyMLine`](firmware/note_detector/note_detector.ino) (lines 101–111).

**Note:** The Python app no longer sends `M` for grading; this path remains **optional** on the device for compatibility and debugging.

---

### 6 — `C` / `P` / `S` protocol (replace Python `M` batch) — **Major**

Host sends a multi-line frame: clear buffer, set each physical pixel explicitly, then show. Python maps logical feedback slots 0..7 to physical indices via `NEOPIXEL_PHYSICAL_INDICES` (and optional reversal).

**Code today**

- Indices: [`NEOPIXEL_REVERSE_STRIP`](moderator/game_logic.py) (lines 11–12), [`_feedback_physical_indices`](moderator/game_logic.py) (lines 15–17), [`NEOPIXEL_PHYSICAL_INDICES`](moderator/game_logic.py) (lines 20–21).
- Frame builder: [`format_neopixel_feedback_serial`](moderator/game_logic.py) (lines 85–100); also [`format_neopixel_all_green_serial`](moderator/game_logic.py) (lines 103–109), [`format_neopixel_clear_serial`](moderator/game_logic.py) (lines 112–113).
- Firmware: [`applyPixelLine`](firmware/note_detector/note_detector.ino) (lines 113–128); [`readLEDCommand`](firmware/note_detector/note_detector.ino) (lines 202–207) for `C`, `S`, and `P`.

---

### 7 — Sticky NeoPixel feedback — **Minor**

Hardware colors are **not** cleared on P1 submit or feedback Continue; they stay until the next grading frame (which starts with `C`) or **New round**.

**Code today**

- [`_p1_submit`](moderator/main_window.py) (lines 515–529) — no clear call.
- [`_feedback_continue`](moderator/main_window.py) (lines 572–581) — no clear call.
- Explicit clear only on new round + comment: [`_new_round`](moderator/main_window.py) (lines 583–595).

---

### 8 — Sequential 1s-per-LED feedback — **Minor (reverted)**

Briefly, non-perfect grades stepped through LEDs one per second, then cleared. That experiment was **removed**; behavior is again **one** `C`/`P`×8/`S` update per grade.

**Code today (restored instant path)**

- [`send_led`](moderator/receiver.py) (lines 28–30) → [`format_neopixel_feedback_serial`](moderator/game_logic.py) (lines 85–100).

---

### 9 — Hardware alignment toggles — **Minor**

Strip **color order** (GRB vs RGB) and **data-in direction** vs logical slot order.

**Code today**

- Python: [`NEOPIXEL_REVERSE_STRIP`](moderator/game_logic.py) (lines 11–21).
- Firmware: [`MODERATOR_NEOPIXEL_TYPE`](firmware/note_detector/note_detector.ino) (lines 25–36); NeoPixel constructor (line 36). Optional sparse wiring: [`LED_MAP`](firmware/note_detector/note_detector.ino) (lines 47–48).

---

## Historical note (Python `M` batch)

Early sessions used a single-line `M r0 g0 b0 …` helper on the host. That API is **gone** from Python; the firmware still implements **`parseMLine24` / `applyMLine`** ([`firmware/note_detector/note_detector.ino`](firmware/note_detector/note_detector.ino) lines 68–111) for optional use.
