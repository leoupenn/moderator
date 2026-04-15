"""Parse lines like `[0, 1, 0, ...]` (16 ints) from MPR121 note_detector firmware."""
from __future__ import annotations

import ast
from typing import List, Optional

from .game_logic import SLOTS, normalize_pattern


def parse_line(line: str) -> Optional[List[int]]:
    line = line.strip()
    if not (line.startswith("[") and line.endswith("]")):
        return None
    try:
        arr = ast.literal_eval(line)
        if isinstance(arr, list) and len(arr) == 16:
            vals = [int(x) for x in arr]
            if all(v in (0, 1) for v in vals):
                return vals
    except (ValueError, SyntaxError, TypeError):
        pass
    return None


def validate_sensed_pattern(values: List[int]) -> bool:
    """
    True only if the controller reported a sane binary touch frame (0/1 per slot).
    Reject corrupt or non-binary values so UI / playback ignore sensing errors.
    """
    try:
        p = normalize_pattern(list(values))
    except (TypeError, ValueError):
        return False
    if len(p) != SLOTS:
        return False
    return all(x in (0, 1) for x in p)
