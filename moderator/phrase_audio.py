"""One-bar phrase audio: sustained sine gated by even-start / odd-end FIFO note rules."""
from __future__ import annotations

import math
import struct
from typing import Final, List, Tuple

from .game_logic import SLOTS, normalize_pattern

SAMPLE_RATE: Final[int] = 44100

# ~4 ms slew at note on/off boundaries
EDGE_RAMP_S: Final[float] = 0.004

# Silence between back-to-back notes (end at step e, next start at e+1).
# Scales with 16th-note length so separation stays musical; floor/max keep it audible.
NOTE_GAP_MIN_S: Final[float] = 0.034
NOTE_GAP_MAX_S: Final[float] = 0.072
NOTE_GAP_FRACTION_OF_STEP: Final[float] = 0.52


def note_intervals_from_pattern(pattern: List[int]) -> List[Tuple[int, int]]:
    """
    Start events: even index, truthy. End events: odd index, truthy.
    FIFO: each end closes the oldest unmatched start. Inclusive (start_step, end_step).
    Unmatched starts after the scan hold through step SLOTS - 1.
    Stray ends (no open start) are ignored.
    """
    p = normalize_pattern(pattern)
    queue: List[int] = []
    intervals: List[Tuple[int, int]] = []

    for i in range(SLOTS):
        if not bool(p[i]):
            continue
        if i % 2 == 0:
            queue.append(i)
        else:
            if queue:
                s = queue.pop(0)
                intervals.append((s, i))

    for s in queue:
        intervals.append((s, SLOTS - 1))

    return intervals


def _gate_per_step(pattern: List[int]) -> List[bool]:
    """True if any note sounds during that step index (0..15)."""
    gate = [False] * SLOTS
    for s, e in note_intervals_from_pattern(pattern):
        for k in range(s, min(e, SLOTS - 1) + 1):
            gate[k] = True
    return gate


def _note_audio_intervals_s(
    pattern: List[int], step_duration_s: float
) -> List[Tuple[float, float]]:
    """
    Half-open time ranges [t0, t1) where the sine should sound.
    If one note ends at step e and the next begins at e+1, insert silence between
    them (at least NOTE_GAP_MIN_S, ~52% of one step, capped at NOTE_GAP_MAX_S).
    """
    d = step_duration_s
    note_iv = sorted(note_intervals_from_pattern(pattern), key=lambda x: x[0])
    gap = min(NOTE_GAP_MAX_S, max(NOTE_GAP_MIN_S, d * NOTE_GAP_FRACTION_OF_STEP))
    half = gap * 0.5
    out: List[Tuple[float, float]] = []

    for i, (s, e) in enumerate(note_iv):
        t0 = s * d
        t1 = (e + 1) * d
        if i > 0:
            sp, ep = note_iv[i - 1]
            if s == ep + 1:
                t0 += half
        if i < len(note_iv) - 1:
            sn, en = note_iv[i + 1]
            if sn == e + 1:
                t1 -= half
        if t1 > t0 + 1e-9:
            out.append((t0, t1))

    return out


def render_held_sine_phrase(
    pattern: List[int],
    *,
    step_duration_s: float,
    sample_rate: int,
    channels: int,
    encoding: str,
    freq_hz: float = 440.0,
    volume: float = 0.85,
) -> bytes:
    """
    Renders exactly one bar: 16 * step_duration_s seconds of interleaved PCM.
    encoding: 'int16' or 'float32'
    """
    T = SLOTS * step_duration_s
    num_samples = max(1, int(round(T * sample_rate)))
    ch = max(1, channels)
    audio_iv = _note_audio_intervals_s(pattern, step_duration_s)

    def gate_at(time_s: float) -> bool:
        return any(t0 <= time_s < t1 for t0, t1 in audio_iv)

    ramp_n = max(1, int(round(sample_rate * EDGE_RAMP_S)))
    slew = 1.0 / float(ramp_n)

    out = bytearray()
    g_smooth = 0.0

    t_max = step_duration_s * SLOTS
    for n in range(num_samples):
        t = (n + 0.5) / sample_rate
        t_clamped = min(t, t_max - 1e-9)
        target = 1.0 if gate_at(t_clamped) else 0.0
        if g_smooth < target:
            g_smooth = min(target, g_smooth + slew)
        elif g_smooth > target:
            g_smooth = max(target, g_smooth - slew)

        sample = volume * g_smooth * math.sin(2 * math.pi * freq_hz * t)

        if encoding == "int16":
            v = int(max(-32767, min(32767, sample * 32767)))
            for _ in range(ch):
                out += struct.pack("<h", v)
        elif encoding == "float32":
            f = max(-1.0, min(1.0, sample))
            for _ in range(ch):
                out += struct.pack("<f", f)
        else:
            raise ValueError(f"Unknown encoding: {encoding}")

    return bytes(out)
