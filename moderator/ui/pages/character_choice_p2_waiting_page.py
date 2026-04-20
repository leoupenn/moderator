"""Figma 29:808 — 'Waiting for other player…' with P2 character pick underneath.

The Figma file shows a modal overlay over the same character strip; on the
desktop we surface the Player 2 picker first, then auto-advance once both
players have confirmed.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...session import FlowState
from ..theme import DESIGN_W, THEME
from ..widgets import CharacterStrip, ChoiceButton, ChoiceStyle, FlowPage


class CharacterChoiceP2WaitingPage(FlowPage):
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

        sub = QLabel("PLAYER 2 — PICK YOUR DUCK", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(45, 169)

        self._strip = CharacterStrip("Player 2", self)
        self._strip.move((DESIGN_W - 648) // 2, 271)
        self._strip.set_current(flow.character_p2)

        confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        confirm.move((DESIGN_W - 334) // 2, 858)
        confirm.clicked.connect(self._on_confirm)

        self._overlay = self._build_overlay()
        self._overlay.hide()

    def on_enter(self) -> None:
        self._strip.set_current(self.flow.character_p2)
        self._overlay.hide()

    def _on_confirm(self) -> None:
        self.flow.character_p2 = self._strip.current()
        self._overlay.show()
        self._overlay.raise_()
        QTimer.singleShot(1100, self._finish)

    def _finish(self) -> None:
        self._overlay.hide()
        self.confirmed.emit()

    def _build_overlay(self) -> QFrame:
        scrim = QFrame(self)
        scrim.setObjectName("Scrim")
        scrim.setGeometry(0, 0, DESIGN_W, self.height())

        modal = QFrame(scrim)
        modal.setObjectName("WaitingModal")
        modal.setFixedSize(730, 300)
        modal.move((DESIGN_W - 730) // 2, (self.height() - 300) // 2)

        col = QVBoxLayout(modal)
        col.setContentsMargins(60, 40, 60, 40)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Ready!", modal)
        label.setObjectName("WaitingTitle")
        f = QFont(THEME.font_display)
        f.setPixelSize(96)
        label.setFont(f)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(label)

        sub = QLabel("Let the match begin…", modal)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(36)
        sub.setFont(sf)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(sub)
        return scrim
