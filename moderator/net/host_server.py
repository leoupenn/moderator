"""Host-side TCP server: accepts one client (Player 2) and pumps messages.

The accept + read loop runs on a background ``QThread``; inbound messages are
re-emitted as Qt signals on the main thread for easy UI wiring. Outbound
messages are queued on an internal lock-guarded list and flushed by the worker
thread, so call sites never block on I/O.
"""
from __future__ import annotations

import socket
import threading
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .protocol import decode_messages


DEFAULT_PORT = 8769


class _HostWorker(QObject):
    """Runs inside a QThread. Owns the listening socket + the accepted peer."""

    client_connected = Signal(str)          # remote address "host:port"
    client_disconnected = Signal(str)       # reason
    message_received = Signal(dict)         # decoded JSON message
    listening = Signal(int)                 # bound port
    error = Signal(str)
    stopped = Signal()

    def __init__(self, port: int) -> None:
        super().__init__()
        self._port = port
        self._server: Optional[socket.socket] = None
        self._peer: Optional[socket.socket] = None
        self._running = True
        self._send_lock = threading.Lock()
        self._send_queue: List[bytes] = []

    # ----- thread entry ---------------------------------------------------
    def run(self) -> None:
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind(("0.0.0.0", self._port))
            self._server.listen(1)
            # Use a short timeout so we can check self._running between accepts.
            self._server.settimeout(0.5)
            # Report the actually-bound port (may differ from requested when
            # callers pass 0 for "ephemeral").
            bound_port = self._server.getsockname()[1]
            self._port = bound_port
            self.listening.emit(bound_port)
        except OSError as exc:
            self.error.emit(f"Could not bind port {self._port}: {exc}")
            self.stopped.emit()
            return

        while self._running:
            try:
                conn, addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError as exc:
                if self._running:
                    self.error.emit(f"accept() failed: {exc}")
                break

            if self._peer is not None:
                # Only one player slot in this MVP; politely drop extras.
                try:
                    conn.sendall(b'{"type":"error","reason":"slot_taken"}\n')
                finally:
                    conn.close()
                continue

            self._peer = conn
            self._peer.settimeout(0.5)
            peer_addr = f"{addr[0]}:{addr[1]}"
            self.client_connected.emit(peer_addr)
            self._serve_peer()
            self._peer = None

        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        self.stopped.emit()

    # ----- per-peer I/O loop ---------------------------------------------
    def _serve_peer(self) -> None:
        assert self._peer is not None
        buf = bytearray()
        reason = "disconnected"
        while self._running:
            # Drain outgoing queue first so responses are low-latency.
            if not self._flush_outgoing():
                reason = "send_failed"
                break
            try:
                chunk = self._peer.recv(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                reason = f"recv_error:{exc}"
                break
            if not chunk:
                reason = "peer_closed"
                break
            buf.extend(chunk)
            for msg in decode_messages(buf):
                self.message_received.emit(msg)

        try:
            self._peer.close()
        except OSError:
            pass
        self.client_disconnected.emit(reason)

    def _flush_outgoing(self) -> bool:
        with self._send_lock:
            pending = self._send_queue[:]
            self._send_queue.clear()
        if not pending:
            return True
        assert self._peer is not None
        try:
            for frame in pending:
                self._peer.sendall(frame)
        except OSError:
            return False
        return True

    # ----- thread-safe control from UI thread -----------------------------
    def enqueue(self, frame: bytes) -> None:
        with self._send_lock:
            self._send_queue.append(frame)

    def request_stop(self) -> None:
        self._running = False
        # Unblock a potentially blocked recv/accept by shutting the sockets.
        if self._peer is not None:
            try:
                self._peer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass


class HostServer(QObject):
    """UI-side facade. Starts/stops the background worker + rebroadcasts events."""

    listening = Signal(int)
    client_connected = Signal(str)
    client_disconnected = Signal(str)
    message_received = Signal(dict)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_HostWorker] = None

    # ----- lifecycle ------------------------------------------------------
    def start(self, port: int = DEFAULT_PORT) -> None:
        if self._worker is not None:
            return
        thread = QThread(self)
        worker = _HostWorker(port)
        worker.moveToThread(thread)
        worker.listening.connect(self.listening.emit)
        worker.client_connected.connect(self.client_connected.emit)
        worker.client_disconnected.connect(self.client_disconnected.emit)
        worker.message_received.connect(self.message_received.emit)
        worker.error.connect(self.error.emit)
        worker.stopped.connect(thread.quit)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.request_stop()
        if self._thread is not None:
            self._thread.wait(2000)
        self._worker = None
        self._thread = None

    # ----- send -----------------------------------------------------------
    def send_frame(self, frame: bytes) -> None:
        if self._worker is not None:
            self._worker.enqueue(frame)

    @property
    def is_running(self) -> bool:
        return self._worker is not None
