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

from typing import Optional

from PySide6.QtCore import QObject, Signal

from ..session import FlowState, NetworkRole
from .client_connection import DEFAULT_PORT as CLIENT_DEFAULT_PORT
from .client_connection import ClientConnection
from .host_server import DEFAULT_PORT as HOST_DEFAULT_PORT
from .host_server import HostServer
from .protocol import (
    MSG_HELLO,
    PROTOCOL_VERSION,
    encode_message,
)


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

    def __init__(self, flow: FlowState, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._flow = flow
        self._host: Optional[HostServer] = None
        self._client: Optional[ClientConnection] = None

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
        host.message_received.connect(self.message_received.emit)
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
        client.message_received.connect(self.message_received.emit)
        client.error.connect(self._on_client_error)
        self._client = client
        client.start(host_ip, port)

    def stop(self) -> None:
        if self._host is not None:
            self._host.stop()
            self._host = None
        if self._client is not None:
            self._client.stop()
            self._client = None
        self._flow.network_role = NetworkRole.SOLO
        self._flow.local_player = 1
        self._flow.network_status = ""

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
        self.client_connected.emit()

    def _on_client_disconnected(self, reason: str) -> None:
        self._flow.network_status = f"Disconnected from host ({reason})"
        self.status.emit(self._flow.network_status)
        self.client_disconnected.emit(reason)

    def _on_client_error(self, msg: str) -> None:
        self._flow.network_status = f"Client error: {msg}"
        self.status.emit(self._flow.network_status)
        self.error.emit(msg)
