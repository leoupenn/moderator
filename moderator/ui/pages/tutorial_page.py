"""Figma 8:58 — Tutorial ('Welcome to Beat IT! — How familiar are you...')."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ...session import Difficulty, FlowState
from ._binary_choice import BinaryChoicePage


class TutorialPage(BinaryChoicePage):
    difficulty_selected = Signal(object)  # Difficulty

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Welcome to Beat IT!",
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
