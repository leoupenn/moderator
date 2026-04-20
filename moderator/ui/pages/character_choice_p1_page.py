"""Figma 21:606 — Competition Character Choice (Player 1 view)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...session import FlowState
from ..theme import DESIGN_W, THEME
from ..widgets import CharacterStrip, ChoiceButton, ChoiceStyle, FlowPage


class CharacterChoiceP1Page(FlowPage):
    confirmed = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("CHOOSE YOUR CHARACTER", self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(45, 32)

        sub = QLabel("WHAT DUCK WOULD YOU LIKE?", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(45, 169)

        self._strip = CharacterStrip("Player 1", self)
        self._strip.move((DESIGN_W - 648) // 2, 271)
        self._strip.set_current(flow.character_p1)

        confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        confirm.move((DESIGN_W - 334) // 2, 858)
        confirm.clicked.connect(self._on_confirm)

    def on_enter(self) -> None:
        self._strip.set_current(self.flow.character_p1)

    def _on_confirm(self) -> None:
        self.flow.character_p1 = self._strip.current()
        self.confirmed.emit()
