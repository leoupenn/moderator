"""Turn-based rhythm game rules and rhythm slot semantics."""
from __future__ import annotations

from enum import Enum, auto
from typing import List, Literal, Tuple

SLOTS = 16
MAX_FAILED_ATTEMPTS = 5
# note_detector.ino exposes 8 logical NeoPixels (pairs of S/E slots share one LED).
# Serial frames use feedback indices 0..7; firmware maps via LED_MAP to strip pixels.
NEOPIXEL_FEEDBACK_COUNT = 8


class Phase(Enum):
    P1_INPUT = auto()
    P2_INPUT = auto()
    FEEDBACK = auto()
    ROUND_WON = auto()
    ROUND_LOST_REVEAL = auto()


def slot_role(index: int) -> Literal["start", "end"]:
    """Even indices (0,2,…): note start; odd indices (1,3,…): note end."""
    return "start" if index % 2 == 0 else "end"


def normalize_pattern(raw: List[int]) -> List[int]:
    return [int(x) for x in raw[:SLOTS]] + [0] * max(0, SLOTS - len(raw))


def binary_pattern_for_playback(raw: List[int]) -> List[int]:
    """Clamp to strict 0/1 after normalize — rhythm audio always sees valid binary steps."""
    p = normalize_pattern(raw)
    return [1 if x else 0 for x in p]


def compare_patterns(reference: List[int], attempt: List[int]) -> Tuple[List[bool], int]:
    """
    Per-slot match: True if reference[i] == attempt[i] (same presence for that role).
    Returns (matches_16, num_correct).
    """
    a = normalize_pattern(reference)
    b = normalize_pattern(attempt)
    matches = [a[i] == b[i] for i in range(SLOTS)]
    return matches, sum(matches)


def feedback_led_chars(matches: List[bool]) -> List[str]:
    """'G' correct, 'R' wrong — one character per slot for UI."""
    return ["G" if m else "R" for m in matches]


def neopixel_rgb_for_feedback_led(matches: List[bool], led_index: int) -> Tuple[int, int, int]:
    """
    RGB for one feedback NeoPixel (led_index 0..7). Same rule for every index: rhythm
    slots (2*led_index, 2*led_index+1) must both match for green, else red.
    """
    if len(matches) != SLOTS:
        raise ValueError("Need 16 match flags")
    if led_index < 0 or led_index >= NEOPIXEL_FEEDBACK_COUNT:
        raise ValueError("led_index must be 0..7")
    i0 = 2 * led_index
    i1 = i0 + 1
    ok = matches[i0] and matches[i1]
    return (0, 255, 0) if ok else (255, 0, 0)


def matches_to_neopixel_rgb(matches: List[bool]) -> List[Tuple[int, int, int]]:
    """
    Map 16 per-slot results to 8 NeoPixel colors — one call per feedback index 0..7.
    """
    return [neopixel_rgb_for_feedback_led(matches, k) for k in range(NEOPIXEL_FEEDBACK_COUNT)]


def _format_neopixel_m_line(colors: List[Tuple[int, int, int]]) -> str:
    """
    Single-line ``M r0 g0 b0 ... r7 g7 b7`` frame for note_detector.ino.

    One USB line produces exactly one ``strip.show()`` on the device. The
    firmware parser rejects the line atomically if it arrives short (e.g. a
    USB-CDC packet split mid-frame), so a truncated write leaves the
    previous image showing instead of half-updating the strip.
    """
    if len(colors) != NEOPIXEL_FEEDBACK_COUNT:
        raise ValueError(f"Need {NEOPIXEL_FEEDBACK_COUNT} RGB triples")
    nums = [str(v) for rgb in colors for v in rgb]
    return "M " + " ".join(nums) + "\n"


def format_neopixel_feedback_serial(matches: List[bool]) -> str:
    """Single-line ``M`` frame painting the eight feedback LEDs red/green."""
    return _format_neopixel_m_line(matches_to_neopixel_rgb(matches))


def format_neopixel_all_green_serial() -> str:
    """Single-line ``M`` frame with every feedback LED green (perfect round)."""
    return _format_neopixel_m_line([(0, 255, 0)] * NEOPIXEL_FEEDBACK_COUNT)


def format_neopixel_clear_serial() -> str:
    """Single-line ``M`` frame blacking out all eight feedback LEDs."""
    return _format_neopixel_m_line([(0, 0, 0)] * NEOPIXEL_FEEDBACK_COUNT)
