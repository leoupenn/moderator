"""Thread-safe NeoPixel commands to the serial worker (C / P i r g b / S frames)."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .game_logic import format_neopixel_feedback_serial

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
    short = line.strip().replace("\n", "")
    if len(short) > 72:
        short = short[:72] + "…"
    return f"Sent: {short!r}"


def send_led(worker: Optional[SerialReaderWorker], matches: List[bool]) -> str:
    """Send all 8 feedback colors in one C / P×8 / S frame."""
    return send_m_line(worker, format_neopixel_feedback_serial(matches))
