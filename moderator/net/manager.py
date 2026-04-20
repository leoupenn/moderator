"""Thin coordinator that owns the host/client transport and exposes a small
Qt-signal surface the MainWindow can listen to.

Responsibilities:
- Start/stop host or client based on ``FlowState.network_role``.
- Broadcast FlowState snapshots + nav commands from the host.
- Re-emit inbound messages for the MainWindow to apply (nav, state, submit,
  round_result, etc.).

The manager itself is intentionally dumb about game logic — the MainWindow is
still the brain and calls into ``FlowState`` / ``GameSession``.
"""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from ..session import FlowState, NetworkRole
from .client_connection import DEFAULT_PORT as CLIENT_DEFAULT_PORT
from .client_connection import ClientConnection
from .host_server import DEFAULT_PORT as HOST_DEFAULT_PORT
from .host_server import HostServer
from .protocol import (
    MSG_HELLO,
    MSG_TIME_SYNC_REQ,
    MSG_TIME_SYNC_RESP,
    PROTOCOL_VERSION,
    encode_message,
)


# Number of sync probes and spacing between them when the client first
# connects. A short burst is enough to lock in a low-RTT sample; we keep the
# best one rather than averaging so a single lucky packet dominates the noise.
_SYNC_SAMPLES_ON_CONNECT = 5
_SYNC_INTERVAL_MS = 500


class NetworkManager(QObject):
    # Host signals
    host_listening = Signal(int)            # port
    host_client_connected = Signal(str)     # peer address
    host_client_disconnected = Signal(str)  # reason

    # Client signals
    client_connected = Signal()
    client_disconnected = Signal(str)

    # Shared
    message_received = Signal(dict)         # decoded inbound message
    status = Signal(str)                    # human-readable status update
    error = Signal(str)
    clock_synced = Signal(float, float)     # (offset_ms, rtt_ms)

    def __init__(self, flow: FlowState, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._flow = flow
        self._host: Optional[HostServer] = None
        self._client: Optional[ClientConnection] = None

        # NTP-style clock-offset state. ``_clock_offset_ms`` is
        # ``host_clock_ms - client_clock_ms`` (positive when the host's wall
        # clock runs ahead of the client's). On the host it's always 0 — it
        # IS the reference.
        self._clock_offset_ms: float = 0.0
        self._clock_rtt_ms: float = 0.0
        self._clock_synced: bool = False
        self._clock_sync_best_rtt_ms: float = float("inf")
        self._clock_sync_samples_remaining: int = 0
        self._clock_sync_timer: Optional[QTimer] = None

    # ----- role control ---------------------------------------------------
    def start_host(self, port: int = HOST_DEFAULT_PORT) -> None:
        self.stop()
        self._flow.network_role = NetworkRole.HOST
        self._flow.host_port = port
        self._flow.local_player = 1
        host = HostServer(self)
        host.listening.connect(self._on_host_listening)
        host.client_connected.connect(self._on_host_peer_connected)
        host.client_disconnected.connect(self._on_host_peer_disconnected)
        host.message_received.connect(self._on_inbound_message)
        host.error.connect(self._on_host_error)
        self._host = host
        host.start(port)

    def start_client(self, host_ip: str, port: int = CLIENT_DEFAULT_PORT) -> None:
        self.stop()
        self._flow.network_role = NetworkRole.CLIENT
        self._flow.host_ip = host_ip
        self._flow.host_port = port
        self._flow.local_player = 2
        client = ClientConnection(self)
        client.connected.connect(self._on_client_connected)
        client.disconnected.connect(self._on_client_disconnected)
        client.message_received.connect(self._on_inbound_message)
        client.error.connect(self._on_client_error)
        self._client = client
        client.start(host_ip, port)

    def stop(self) -> None:
        if self._clock_sync_timer is not None:
            self._clock_sync_timer.stop()
        if self._host is not None:
            self._host.stop()
            self._host = None
        if self._client is not None:
            self._client.stop()
            self._client = None
        self._flow.network_role = NetworkRole.SOLO
        self._flow.local_player = 1
        self._flow.network_status = ""
        self._clock_offset_ms = 0.0
        self._clock_rtt_ms = 0.0
        self._clock_synced = False
        self._clock_sync_best_rtt_ms = float("inf")
        self._clock_sync_samples_remaining = 0

    # ----- send helpers ---------------------------------------------------
    def send(self, msg_type: str, **fields) -> None:
        """Send a message to the peer (whichever direction makes sense)."""
        frame = encode_message(msg_type, **fields)
        if self._host is not None and self._host.is_running:
            self._host.send_frame(frame)
        elif self._client is not None and self._client.is_running:
            self._client.send_frame(frame)

    @property
    def is_host(self) -> bool:
        return self._host is not None

    @property
    def is_client(self) -> bool:
        return self._client is not None

    # ----- clock sync -----------------------------------------------------
    @property
    def clock_offset_ms(self) -> float:
        """Best-known ``host_clock_ms - client_clock_ms`` measured by sync."""
        return self._clock_offset_ms

    @property
    def clock_rtt_ms(self) -> float:
        return self._clock_rtt_ms

    @property
    def is_clock_synced(self) -> bool:
        """True once at least one successful NTP-style sample has landed."""
        return self._clock_synced

    def host_to_local_ms(self, host_ms: float) -> int:
        """Convert a host wall-clock timestamp (ms) into this machine's
        ``time.time() * 1000`` frame of reference. On the host this is a
        no-op; on the client it subtracts the measured clock offset so the
        two machines agree on ``elapsed = now - start``."""
        return int(host_ms - self._clock_offset_ms)

    def local_to_host_ms(self, local_ms: float) -> int:
        """Inverse of :meth:`host_to_local_ms`."""
        return int(local_ms + self._clock_offset_ms)

    def _start_clock_sync(
        self,
        samples: int = _SYNC_SAMPLES_ON_CONNECT,
        interval_ms: int = _SYNC_INTERVAL_MS,
    ) -> None:
        """Kick off a short burst of NTP probes from the client.

        Multiple samples let us pick the one with the lowest RTT — that's
        the most accurate because it means the request and response each
        spent roughly half the RTT in flight (the symmetry assumption NTP
        relies on).
        """
        if not self.is_client:
            return
        self._clock_sync_samples_remaining = max(1, int(samples))
        self._clock_sync_best_rtt_ms = float("inf")
        if self._clock_sync_timer is None:
            self._clock_sync_timer = QTimer(self)
            self._clock_sync_timer.timeout.connect(self._send_time_sync_req)
        self._clock_sync_timer.start(max(50, int(interval_ms)))
        self._send_time_sync_req()

    def _send_time_sync_req(self) -> None:
        if not self.is_client:
            if self._clock_sync_timer is not None:
                self._clock_sync_timer.stop()
            return
        if self._clock_sync_samples_remaining <= 0:
            if self._clock_sync_timer is not None:
                self._clock_sync_timer.stop()
            return
        self._clock_sync_samples_remaining -= 1
        t1 = int(time.time() * 1000)
        self.send(MSG_TIME_SYNC_REQ, t1=t1)

    def _handle_time_sync_req(self, msg: dict) -> None:
        # Host side: stamp t2 as early as possible and t3 as late as possible
        # so the sample captures the true host processing window.
        t2 = int(time.time() * 1000)
        try:
            t1 = int(msg.get("t1", 0))
        except (TypeError, ValueError):
            return
        t3 = int(time.time() * 1000)
        self.send(MSG_TIME_SYNC_RESP, t1=t1, t2=t2, t3=t3)

    def _handle_time_sync_resp(self, msg: dict) -> None:
        t4 = int(time.time() * 1000)
        try:
            t1 = int(msg["t1"])
            t2 = int(msg["t2"])
            t3 = int(msg["t3"])
        except (KeyError, TypeError, ValueError):
            return
        offset = ((t2 - t1) + (t3 - t4)) / 2.0
        rtt = max(0.0, float((t4 - t1) - (t3 - t2)))
        if rtt < self._clock_sync_best_rtt_ms:
            self._clock_sync_best_rtt_ms = rtt
            self._clock_offset_ms = offset
            self._clock_rtt_ms = rtt
            self._clock_synced = True
            self.clock_synced.emit(offset, rtt)
        if (
            self._clock_sync_samples_remaining <= 0
            and self._clock_sync_timer is not None
        ):
            self._clock_sync_timer.stop()

    # ----- inbound filter -------------------------------------------------
    def _on_inbound_message(self, msg: dict) -> None:
        """Intercept sync traffic here so it never reaches MainWindow."""
        kind = msg.get("type")
        if kind == MSG_TIME_SYNC_REQ and self.is_host:
            self._handle_time_sync_req(msg)
            return
        if kind == MSG_TIME_SYNC_RESP and self.is_client:
            self._handle_time_sync_resp(msg)
            return
        self.message_received.emit(msg)

    # ----- host callbacks -------------------------------------------------
    def _on_host_listening(self, port: int) -> None:
        self._flow.network_status = f"Hosting on port {port} — waiting for Player 2…"
        self.status.emit(self._flow.network_status)
        self.host_listening.emit(port)

    def _on_host_peer_connected(self, addr: str) -> None:
        self._flow.network_status = f"Player 2 connected from {addr}"
        self.status.emit(self._flow.network_status)
        self.host_client_connected.emit(addr)

    def _on_host_peer_disconnected(self, reason: str) -> None:
        self._flow.network_status = f"Player 2 disconnected ({reason})"
        self.status.emit(self._flow.network_status)
        self.host_client_disconnected.emit(reason)

    def _on_host_error(self, msg: str) -> None:
        self._flow.network_status = f"Host error: {msg}"
        self.status.emit(self._flow.network_status)
        self.error.emit(msg)

    # ----- client callbacks ----------------------------------------------
    def _on_client_connected(self) -> None:
        self._flow.network_status = f"Connected to {self._flow.host_ip} as Player 2"
        self.status.emit(self._flow.network_status)
        # Introduce ourselves so the host can welcome / assign player id.
        self.send(MSG_HELLO, role="client", version=PROTOCOL_VERSION)
        # Lock in a clock-offset estimate right away — any gameplay message
        # that carries a host timestamp can then be translated into this
        # machine's clock frame (see ``host_to_local_ms``).
        self._start_clock_sync()
        self.client_connected.emit()

    def _on_client_disconnected(self, reason: str) -> None:
        self._flow.network_status = f"Disconnected from host ({reason})"
        self.status.emit(self._flow.network_status)
        self.client_disconnected.emit(reason)

    def _on_client_error(self, msg: str) -> None:
        self._flow.network_status = f"Client error: {msg}"
        self.status.emit(self._flow.network_status)
        self.error.emit(msg)
