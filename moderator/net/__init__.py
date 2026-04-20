"""LAN networking for two-machine multiplayer (Host on P1, Client on P2)."""
from .client_connection import ClientConnection
from .host_server import HostServer
from .manager import NetworkManager
from .protocol import (
    MSG_ABORT_TO_HOME,
    MSG_ATTEMPTS_UPDATE,
    MSG_CHARACTER_SELECT,
    MSG_HELLO,
    MSG_INPUT_PATTERN,
    MSG_NAV,
    MSG_PLAY_REFERENCE,
    MSG_READY,
    MSG_ROUND_RESULT,
    MSG_START_ROUND,
    MSG_STATE,
    MSG_SUBMIT,
    MSG_TIME_SYNC_REQ,
    MSG_TIME_SYNC_RESP,
    MSG_WELCOME,
    PROTOCOL_VERSION,
    decode_messages,
    encode_message,
)
from ..session import NetworkRole

__all__ = [
    "ClientConnection",
    "HostServer",
    "NetworkManager",
    "NetworkRole",
    "MSG_ABORT_TO_HOME",
    "MSG_ATTEMPTS_UPDATE",
    "MSG_CHARACTER_SELECT",
    "MSG_HELLO",
    "MSG_INPUT_PATTERN",
    "MSG_NAV",
    "MSG_PLAY_REFERENCE",
    "MSG_READY",
    "MSG_ROUND_RESULT",
    "MSG_START_ROUND",
    "MSG_STATE",
    "MSG_SUBMIT",
    "MSG_TIME_SYNC_REQ",
    "MSG_TIME_SYNC_RESP",
    "MSG_WELCOME",
    "PROTOCOL_VERSION",
    "decode_messages",
    "encode_message",
]
