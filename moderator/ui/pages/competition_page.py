"""Figma 17:272 — Competitive Mode 'What Competition Form Would you Like?'."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ...session import FlowState, MultiplayerMode
from ._binary_choice import BinaryChoicePage


class CompetitionPage(BinaryChoicePage):
    mode_selected = Signal(object)  # MultiplayerMode

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(
            flow,
            title="Competitive Mode",
            subtitle="What competition form would you like?",
            left_label="Time Challenge",
            right_label="Recreate Rhythm",
            parent=parent,
            show_decorations=False,
        )
        self.connect_left(lambda: self._pick(MultiplayerMode.TIME_CHALLENGE))
        self.connect_right(lambda: self._pick(MultiplayerMode.RECREATE_RHYTHM))

    def _pick(self, m: MultiplayerMode) -> None:
        self.flow.multiplayer_mode = m
        self.mode_selected.emit(m)
