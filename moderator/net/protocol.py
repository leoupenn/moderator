"""Wire protocol for two-machine multiplayer.

Transport: TCP, newline-delimited UTF-8 JSON frames (one message per line).
Direction legend in each docstring: ``H -> C`` host-to-client, ``C -> H`` the
other way. Unknown keys are ignored on receive to keep forward-compat easy.
"""
from __future__ import annotations

import json
from typing import Iterator, List, Optional


# Protocol version; bump whenever the wire format changes incompatibly.
PROTOCOL_VERSION = 1


# ---------- message kinds ---------------------------------------------------
# Client handshake: first thing the client sends after TCP connect.
#   {"type":"hello","role":"client","version":1}
MSG_HELLO = "hello"

# Host acknowledges, assigning a player id (always 2 in MVP).
#   {"type":"welcome","player_id":2,"version":1}
MSG_WELCOME = "welcome"

# Full FlowState snapshot pushed by host so the client can render the current
# screen correctly. Sent on join and whenever the host mutates state.
#   {"type":"state","route":"time_challenge","flow":{...}}
MSG_STATE = "state"

# Explicit navigation command: host tells client to switch screens. Redundant
# with state.route but cheaper to send alone when nothing else changed.
#   {"type":"nav","route":"time_challenge"}
MSG_NAV = "nav"

# Host starts a Time-Challenge round with a shared epoch timestamp and the
# target pattern both UIs render.
#   {"type":"start_round","round":1,"start_epoch_ms":<int>,"target":[0/1 x 16],
#    "bpm":80}
MSG_START_ROUND = "start_round"

# C -> H: client sends its live controller pattern (throttled).
#   {"type":"input_pattern","player":2,"pattern":[0/1 x 16]}
MSG_INPUT_PATTERN = "input_pattern"

# C -> H: client submitted an attempt with the given pattern.
#   {"type":"submit","player":2,"pattern":[0/1 x 16],"client_elapsed_ms":<int>}
MSG_SUBMIT = "submit"

# H -> C: authoritative round result after both players have submitted (or one
# side was force-finished). elapsed_* is authoritative host-measured time.
#   {"type":"round_result","elapsed_p1":<int>,"elapsed_p2":<int>,
#    "attempts_p1":<int>,"attempts_p2":<int>,"winner":1|2|null}
MSG_ROUND_RESULT = "round_result"

# H -> C: host is playing the reference pattern; client can optionally play it
# locally for P2 to hear the same audio cue.
#   {"type":"play_reference"}
MSG_PLAY_REFERENCE = "play_reference"

# H -> C: host returned to welcome (e.g. via the new settings button). Clients
# should reset too and go to a waiting screen.
#   {"type":"abort_to_home"}
MSG_ABORT_TO_HOME = "abort_to_home"

# C -> H: NTP-style clock-sync probe. ``t1`` is the client's ``time.time()`` in
# ms at send time. The host echoes it back in its response so we can pair
# request/response without extra bookkeeping.
#   {"type":"time_sync_req","t1":<client_send_ms>}
MSG_TIME_SYNC_REQ = "time_sync_req"

# H -> C: response to ``time_sync_req``. ``t2`` is the host's clock when the
# request was received, ``t3`` is the host's clock at the moment the response
# was flushed. The client records ``t4`` locally and computes
# ``offset = ((t2 - t1) + (t3 - t4)) / 2`` (host minus client, in ms) and
# ``rtt = (t4 - t1) - (t3 - t2)``.
#   {"type":"time_sync_resp","t1":<int>,"t2":<int>,"t3":<int>}
MSG_TIME_SYNC_RESP = "time_sync_resp"

# C -> H: client player picked a duck on its own machine. Host updates
# ``flow.character_pN`` and rebroadcasts ``MSG_STATE`` so both UIs mirror.
#   {"type":"character_select","player":2,"character":"ducky"}
MSG_CHARACTER_SELECT = "character_select"

# C -> H: the non-host player pressed Confirm / ready on a pregame screen it
# owns (e.g. CharacterChoiceP2). The host advances the shared flow.
#   {"type":"ready","from_player":2,"screen":"char_p2"}
MSG_READY = "ready"


# ---------- encode / decode -------------------------------------------------
def encode_message(msg_type: str, **fields) -> bytes:
    """Serialize a message to a single newline-terminated JSON frame."""
    payload = {"type": msg_type, **fields}
    # ``separators`` keeps lines small; ``ensure_ascii=False`` lets player
    # names with emojis flow through unchanged.
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (line + "\n").encode("utf-8")


def decode_messages(buffer: bytearray) -> Iterator[dict]:
    """Yield complete JSON messages from a growing byte buffer.

    Mutates ``buffer`` in place: consumed bytes are removed so the caller can
    keep appending more socket reads.
    """
    while True:
        nl = buffer.find(b"\n")
        if nl < 0:
            return
        raw = bytes(buffer[:nl])
        del buffer[: nl + 1]
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Skip garbage frames rather than killing the connection; upstream
            # will eventually get a well-formed message.
            continue
        if isinstance(obj, dict) and "type" in obj:
            yield obj


# ---------- small helpers for common payloads ------------------------------
def pattern_is_valid(pattern: Optional[List[int]]) -> bool:
    """Guardrail for untrusted peer patterns before forwarding to game logic."""
    if not isinstance(pattern, list):
        return False
    if len(pattern) > 32:
        return False
    for v in pattern:
        if not isinstance(v, int):
            return False
        if v not in (0, 1):
            return False
    return True
