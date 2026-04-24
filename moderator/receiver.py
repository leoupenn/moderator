"""Thread-safe NeoPixel: ``send_led(worker, pos, r, g, b)`` per line; ``send_led_strip`` for full frames."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional, Tuple

from .game_logic import (
    NEOPIXEL_FEEDBACK_COUNT,
    matches_to_neopixel_rgb,
)

if TYPE_CHECKING:
    from .serial_reader import SerialReaderWorker

# Delay between each ``C`` / ``P`` / ``S`` line when sending a full feedback
# frame (handled in the serial reader thread — does not block the UI).
NEOPIXEL_INTER_COMMAND_DELAY_S = 0.1


def _clamp_channel(v: int) -> int:
    return max(0, min(255, int(v)))


def _p_line(pos: int, r: int, g: int, b: int) -> str:
    """Single ``P <pos> r g b`` command (no newline)."""
    p = int(pos)
    r, g, b = _clamp_channel(r), _clamp_channel(g), _clamp_channel(b)
    return f"P {p} {r} {g} {b}"


def _enqueue_led_line(worker: Optional[SerialReaderWorker], line: str) -> str:
    """Queue exactly one host-to-device line (``C``, ``P …``, ``S``, or a full blob)."""
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    one = line.strip()
    worker.enqueue_line(one + "\n")
    for part in one.split("\n"):
        if part:
            print(f"[led] {part}", flush=True)
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

    For a full strip update use ``send_led_strip`` (``C`` + eight ``P`` + ``S``,
    each on its own serial line — see ``NEOPIXEL_INTER_COMMAND_DELAY_S``).
    """
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    p = int(pos)
    if p < 0 or p >= NEOPIXEL_FEEDBACK_COUNT:
        return f"Invalid LED index {pos!r} (need 0..{NEOPIXEL_FEEDBACK_COUNT - 1})."
    return _enqueue_led_line(worker, _p_line(pos, r, g, b))


def send_led_strip(
    worker: Optional[SerialReaderWorker],
    *,
    matches: Optional[List[bool]] = None,
    preset: Optional[Literal["clear", "all_green"]] = None,
) -> str:
    """
    Queue a ``C`` + eight ``P`` + ``S`` feedback frame.

    Each command is written as its **own** serial line, with a short pause
    (``NEOPIXEL_INTER_COMMAND_DELAY_S``) between lines inside the reader thread.

    ``send_led`` remains available for one-off ``P`` lines (e.g. tooling).

    - ``preset="clear"``: all pixels black.
    - ``preset="all_green"``: all pixels green (perfect round).
    - ``matches``: sixteen slot flags → eight red/green pairs.
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

    lines = ["C"] + [_p_line(i, *rgbs[i]) for i in range(NEOPIXEL_FEEDBACK_COUNT)] + ["S"]
    worker.enqueue_paced_lines(lines, NEOPIXEL_INTER_COMMAND_DELAY_S)
    for part in lines:
        print(f"[led] {part}", flush=True)
    return f"Sent: {' | '.join(lines)!r}"
