"""8-cell rhythm feedback grid, Figma node 31:1126 ('Grid Wordle Feedback').

The internal game model uses 16 slots (pairs of start/end for 8 beats), but the
UI and NeoPixel strip both expose 8 visual cells — one per beat. Each cell's
state is the AND of its two underlying slots:

    cell i  ←→  slots (2i, 2i+1)

Cells are 100 × 135 with 14px rounded corners, sitting inside a dark rounded
container (see Figma "Recreate Rhythm - Recreation", node 21:944 — 1070 × 187).
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from ...game_logic import NEOPIXEL_FEEDBACK_COUNT, SLOTS
from ..theme import THEME


class _Cell(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        size: tuple[int, int] = (100, 135),
        radius: int = 15,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(*size)
        self.setAutoFillBackground(True)
        self._radius = radius
        self._set_color(THEME.rhythm_cell_off)

    def _set_color(self, hex_: str) -> None:
        self.setStyleSheet(
            f"background: {hex_}; border-radius: {self._radius}px; border: none;"
        )

    def set_live(self, on: bool) -> None:
        self._set_color(THEME.rhythm_cell_idle if on else THEME.rhythm_cell_off)

    def set_feedback(self, ok: bool) -> None:
        self._set_color(
            THEME.rhythm_cell_correct if ok else THEME.rhythm_cell_incorrect
        )

    def clear(self) -> None:
        self._set_color(THEME.rhythm_cell_off)


class RhythmTrackGrid(QFrame):
    """Row of 8 pair-cells inside a dark container.

    The public ``set_live_pattern`` / ``set_feedback`` APIs still accept the
    16-slot arrays that the game model produces — we fold adjacent (start, end)
    slots into a single visual cell.
    """

    CELLS = NEOPIXEL_FEEDBACK_COUNT  # 8

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        width: int = 1070,
        height: int = 187,
        cell_size: tuple[int, int] = (100, 135),
        cell_radius: int = 15,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FeedbackGrid")
        self.setFixedSize(width, height)

        row = QHBoxLayout(self)
        v_pad = max(0, (height - cell_size[1]) // 2)
        # Figma container has ~17px horizontal inset.
        row.setContentsMargins(17, v_pad, 17, v_pad)
        row.setSpacing(0)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._cells: list[_Cell] = []
        row.addStretch(1)
        for i in range(self.CELLS):
            c = _Cell(size=cell_size, radius=cell_radius)
            row.addWidget(c)
            self._cells.append(c)
            row.addStretch(1)

    @staticmethod
    def _pair(arr: List, i: int) -> tuple:
        a = arr[2 * i] if 2 * i < len(arr) else 0
        b = arr[2 * i + 1] if 2 * i + 1 < len(arr) else 0
        return a, b

    def set_live_pattern(self, pattern: List[int]) -> None:
        """Light a cell if *either* half of its beat is currently pressed."""
        for i, c in enumerate(self._cells):
            a, b = self._pair(pattern, i)
            c.set_live(bool(a) or bool(b))

    def set_feedback(self, matches: List[bool]) -> None:
        """Green cell iff *both* halves of the beat matched the reference."""
        n = len(matches)
        # Accept either a 16-entry per-slot array or a pre-reduced 8-entry one.
        if n == self.CELLS:
            for i, c in enumerate(self._cells):
                c.set_feedback(bool(matches[i]))
            return
        for i, c in enumerate(self._cells):
            a, b = self._pair(matches, i)
            c.set_feedback(bool(a) and bool(b))

    def clear(self) -> None:
        for c in self._cells:
            c.clear()
