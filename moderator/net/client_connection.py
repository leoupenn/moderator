"""Client-side TCP connection: joins Player-2's machine to the host session."""
from __future__ import annotations

import socket
import threading
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .protocol import decode_messages


DEFAULT_PORT = 8769


class _ClientWorker(QObject):
    """Connects to host and runs a recv loop on its own thread."""

    connected = Signal()
    disconnected = Signal(str)
    message_received = Signal(dict)
    error = Signal(str)
    stopped = Signal()

    def __init__(self, host_ip: str, port: int) -> None:
        super().__init__()
        self._host_ip = host_ip
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._running = True
        self._send_lock = threading.Lock()
        self._send_queue: List[bytes] = []

    def run(self) -> None:
        try:
            self._sock = socket.create_connection(
                (self._host_ip, self._port), timeout=4
            )
            self._sock.settimeout(0.5)
        except OSError as exc:
            self.error.emit(f"Could not connect to {self._host_ip}:{self._port}: {exc}")
            self.stopped.emit()
            return

        self.connected.emit()

        buf = bytearray()
        reason = "disconnected"
        while self._running:
            if not self._flush_outgoing():
                reason = "send_failed"
                break
            try:
                chunk = self._sock.recv(4096)
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
            self._sock.close()
        except OSError:
            pass
        self._sock = None
        self.disconnected.emit(reason)
        self.stopped.emit()

    def _flush_outgoing(self) -> bool:
        with self._send_lock:
            pending = self._send_queue[:]
            self._send_queue.clear()
        if not pending or self._sock is None:
            return True
        try:
            for frame in pending:
                self._sock.sendall(frame)
        except OSError:
            return False
        return True

    def enqueue(self, frame: bytes) -> None:
        with self._send_lock:
            self._send_queue.append(frame)

    def request_stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class ClientConnection(QObject):
    """UI-side facade for the client worker."""

    connected = Signal()
    disconnected = Signal(str)
    message_received = Signal(dict)
    error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ClientWorker] = None

    def start(self, host_ip: str, port: int = DEFAULT_PORT) -> None:
        if self._worker is not None:
            return
        thread = QThread(self)
        worker = _ClientWorker(host_ip, port)
        worker.moveToThread(thread)
        worker.connected.connect(self.connected.emit)
        worker.disconnected.connect(self.disconnected.emit)
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

    def send_frame(self, frame: bytes) -> None:
        if self._worker is not None:
            self._worker.enqueue(frame)

    @property
    def is_running(self) -> bool:
        return self._worker is not None
