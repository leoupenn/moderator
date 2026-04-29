"""Figma 17:272 — Competitive Mode 'What Competition Form Would you Like?'."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

from ...session import FlowState, MultiplayerMode, NetworkRole
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

    def on_enter(self) -> None:
        host_owned = self.flow.network_role == NetworkRole.CLIENT
        for btn in (self._left, self._right):
            btn.setEnabled(not host_owned)
            btn.setCursor(
                QCursor(
                    Qt.CursorShape.ArrowCursor
                    if host_owned
                    else Qt.CursorShape.PointingHandCursor
                )
            )

    def _pick(self, m: MultiplayerMode) -> None:
        if self.flow.network_role == NetworkRole.CLIENT:
            return
        self.flow.multiplayer_mode = m
        self.mode_selected.emit(m)
