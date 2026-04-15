"""Short tone burst for rhythm playback (PCM for QAudioSink)."""
from __future__ import annotations

import math
import struct
from typing import Final

SAMPLE_RATE: Final[int] = 44100


def make_stereo_click(
    *,
    sample_rate: int = 44100,
    channels: int = 2,
    encoding: str = "int16",
    freq: float = 800.0,
    duration_s: float = 0.08,
    decay: float = 38.0,
    volume: float = 0.9,
) -> bytes:
    """
    encoding: 'int16' (Qt Int16) or 'float32' (Qt Float32), interleaved channels.
    """
    n = max(1, int(sample_rate * duration_s))
    ch = max(1, channels)
    out = bytearray()

    if encoding == "int16":
        for i in range(n):
            t = i / sample_rate
            s = volume * math.sin(2 * math.pi * freq * t) * math.exp(-t * decay)
            v = int(max(-32767, min(32767, s * 32767)))
            for _ in range(ch):
                out += struct.pack("<h", v)
    elif encoding == "float32":
        for i in range(n):
            t = i / sample_rate
            s = volume * math.sin(2 * math.pi * freq * t) * math.exp(-t * decay)
            f = max(-1.0, min(1.0, s))
            for _ in range(ch):
                out += struct.pack("<f", f)
    else:
        raise ValueError(f"Unknown encoding: {encoding}")

    return bytes(out)
