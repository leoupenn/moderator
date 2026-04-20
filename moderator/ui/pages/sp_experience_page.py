"""Figma 17:242 — Single Player 'How familiar are you with music notation?' pick."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ...session import Difficulty, FlowState
from ._binary_choice import BinaryChoicePage


class SinglePlayerExperiencePage(BinaryChoicePage):
    difficulty_selected = Signal(object)

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Single Player",
            subtitle="How familiar are you with music notation?",
            left_label="Novice",
            right_label="Experienced",
            parent=parent,
        )
        self.connect_left(lambda: self._pick(Difficulty.NOVICE))
        self.connect_right(lambda: self._pick(Difficulty.EXPERIENCED))

    def _pick(self, difficulty: Difficulty) -> None:
        self.flow.difficulty = difficulty
        self.difficulty_selected.emit(difficulty)
