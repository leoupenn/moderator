"""Thread-safe NeoPixel commands: ``send_led(worker, pos, r, g, b)`` per pixel, framed by ``C`` / ``S``."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Literal, Optional, Tuple

from .game_logic import (
    NEOPIXEL_FEEDBACK_COUNT,
    matches_to_neopixel_rgb,
)

if TYPE_CHECKING:
    from .serial_reader import SerialReaderWorker


def _enqueue_led_line(worker: Optional[SerialReaderWorker], line: str) -> str:
    """Queue exactly one host-to-device line (``C``, ``P …``, or ``S``)."""
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    one = line.strip()
    worker.enqueue_line(one + "\n")
    print(f"[led] {one}", flush=True)
    short = one if len(one) <= 72 else one[:72] + "…"
    return f"Sent: {short!r}"


def send_led(
    worker: Optional[SerialReaderWorker],
    pos: int,
    r: int,
    g: int,
    b: int,
) -> str:
    """
    Queue one ``P <pos> r g b`` line (feedback index ``pos`` = 0..7).

    Caller should bracket a full update with ``C`` then eight ``send_led`` calls
    then ``S`` — use ``send_led_strip`` for that.
    """
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    p = int(pos)
    if p < 0 or p >= NEOPIXEL_FEEDBACK_COUNT:
        return f"Invalid LED index {pos!r} (need 0..{NEOPIXEL_FEEDBACK_COUNT - 1})."
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return _enqueue_led_line(worker, f"P {p} {r} {g} {b}")


def send_led_strip(
    worker: Optional[SerialReaderWorker],
    *,
    matches: Optional[List[bool]] = None,
    preset: Optional[Literal["clear", "all_green"]] = None,
) -> str:
    """
    Queue a full strip frame: ``C``, eight per-pixel ``P`` lines via ``send_led``,
    then ``S``. Each line is its own queue item so the serial thread writes them
    separately (avoids multi-line chunks being split awkwardly on the wire).

    - ``preset="clear"``: all pixels black.
    - ``preset="all_green"``: all pixels green (perfect round).
    - ``matches``: sixteen slot flags → eight red/green pairs.

    After ``matches`` or ``preset="all_green"``, sleeps 0.1s when connected.
    """
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    if preset == "clear":
        rgbs: List[Tuple[int, int, int]] = [(0, 0, 0)] * NEOPIXEL_FEEDBACK_COUNT
    elif preset == "all_green":
        rgbs = [(0, 255, 0)] * NEOPIXEL_FEEDBACK_COUNT
    elif matches is not None:
        rgbs = matches_to_neopixel_rgb(matches)
    else:
        return "NeoPixel feedback skipped — pass ``matches`` or ``preset=...``."

    _enqueue_led_line(worker, "C")
    for pos in range(NEOPIXEL_FEEDBACK_COUNT):
        r, g, b = rgbs[pos]
        send_led(worker, pos, r, g, b)
    _enqueue_led_line(worker, "S")

    if preset != "clear":
        time.sleep(0.1)
    return "Sent: NeoPixel frame (C + 8×P + S)"
