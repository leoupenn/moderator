import { io, type Socket } from "socket.io-client";

/**
 * Where Socket.IO listens. In dev we use the same origin as the page so Vite can
 * proxy `/socket.io` to the real server (works for a second player on another machine
 * opening `http://<your-LAN-IP>:5173`). Override with VITE_SOCKET_URL when deployed.
 */
function socketUrl(): string {
  const explicit = import.meta.env.VITE_SOCKET_URL;
  if (explicit && explicit.length > 0) {
    return explicit;
  }
  if (import.meta.env.DEV) {
    // Same host:port as the Vite page → proxy in vite.config.ts forwards to :3847
    return window.location.origin;
  }
  // Production: same URL as the site (one host serves static + Socket.IO, or reverse proxy).
  // For a separate API host, set VITE_SOCKET_URL at build time, e.g. https://api.example.com
  return window.location.origin;
}

let _socket: Socket | null = null;

export function getSocket(): Socket {
  if (!_socket) {
    _socket = io(socketUrl(), {
      path: "/socket.io",
      transports: ["websocket", "polling"],
    });
  }
  return _socket;
}
