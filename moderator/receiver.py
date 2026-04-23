"""Thread-safe NeoPixel commands: single-line ``M`` batch via ``send_led()``."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, Optional

from .game_logic import (
    format_neopixel_all_green_serial,
    format_neopixel_clear_serial,
    format_neopixel_feedback_serial,
)

if TYPE_CHECKING:
    from .serial_reader import SerialReaderWorker


def send_m_line(worker: Optional[SerialReaderWorker], line: str) -> str:
    """
    Queue one line for the reader thread to write (newline added if missing).
    Safe to call from the UI thread — uses a thread-safe queue, not Qt queued signals.
    Returns text suitable for the status label.
    """
    if worker is None:
        return "Not connected — NeoPixel batch not sent (connect XIAO port)."
    worker.enqueue_line(line)
    payload = line.rstrip("\n")
    if payload:
        for cmd in payload.split("\n"):
            print(f"[led] {cmd}", flush=True)
    short = line.strip().replace("\n", "")
    if len(short) > 72:
        short = short[:72] + "…"
    return f"Sent: {short!r}"


def send_led(
    worker: Optional[SerialReaderWorker],
    matches: Optional[List[bool]] = None,
    *,
    preset: Optional[Literal["clear", "all_green"]] = None,
) -> str:
    """
    Queue NeoPixel feedback to the controller.

    - ``matches`` (16 bools): graded red/green per pair (default).
    - ``preset="clear"``: black out all eight feedback LEDs.
    - ``preset="all_green"``: all eight LEDs green (perfect round).
    """
    if preset == "clear":
        return send_m_line(worker, format_neopixel_clear_serial())
    if preset == "all_green":
        return send_m_line(worker, format_neopixel_all_green_serial())
    if matches is None:
        if worker is None:
            return "Not connected — NeoPixel batch not sent (connect XIAO port)."
        return "NeoPixel feedback skipped — pass ``matches`` or ``preset=...``."
    return send_m_line(worker, format_neopixel_feedback_serial(matches))
