"""16-step rhythm feedback grid, Figma node 31:1126 ('Grid Wordle Feedback').

Each cell is 100×135, rounded 14px, inside a dark rounded container. Cells light
up white when active, green on match, red on miss.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from ...game_logic import SLOTS
from ..theme import THEME


class _Cell(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(100, 135)
        self.setAutoFillBackground(True)
        self._set_color(THEME.rhythm_cell_off)

    def _set_color(self, hex_: str) -> None:
        self.setStyleSheet(
            f"background: {hex_}; border-radius: 14px; border: none;"
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
    """Row of 16 cells inside a dark container. No labels — the strip above names it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeedbackGrid")
        self.setFixedSize(1070, 187)

        row = QHBoxLayout(self)
        row.setContentsMargins(17, 26, 17, 26)
        row.setSpacing(0)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._cells: list[_Cell] = []
        for i in range(SLOTS):
            c = _Cell()
            row.addWidget(c)
            self._cells.append(c)
            if i < SLOTS - 1:
                row.addSpacing(0)
        row.insertStretch(0, 1)
        for i in range(SLOTS - 1):
            row.insertStretch(2 + i * 2, 1)
        row.addStretch(1)

    def set_live_pattern(self, pattern: List[int]) -> None:
        for i, c in enumerate(self._cells):
            c.set_live(bool(pattern[i]) if i < len(pattern) else False)

    def set_feedback(self, matches: List[bool]) -> None:
        for i, c in enumerate(self._cells):
            ok = matches[i] if i < len(matches) else False
            c.set_feedback(bool(ok))

    def clear(self) -> None:
        for c in self._cells:
            c.clear()
