"""Figma 8:74 — Introduction.

'Welcome to Beat It!' + 'How familiar are you with Music Notation?' with
Novice / Experienced pills. Coordinates are lifted 1:1 from Figma.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...session import Difficulty, FlowState
from ..theme import THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage


class IntroductionPage(FlowPage):
    """Single-player entry: asks about music-notation familiarity."""

    difficulty_selected = Signal(object)  # Difficulty

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("WELCOME TO BEAT IT!", self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(320, 342)

        subtitle = QLabel("HOW FAMILIAR ARE YOU WITH MUSIC NOTATION?", self)
        subtitle.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        subtitle.setFont(sf)
        subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        subtitle.adjustSize()
        subtitle.move(451, 525)

        novice = ChoiceButton("Novice", ChoiceStyle.BLUE, parent=self)
        novice.move(349, 695)
        novice.clicked.connect(lambda: self._pick(Difficulty.NOVICE))

        experienced = ChoiceButton("Experienced", ChoiceStyle.YELLOW, parent=self)
        experienced.move(821, 695)
        experienced.clicked.connect(lambda: self._pick(Difficulty.EXPERIENCED))

    def _pick(self, diff: Difficulty) -> None:
        self.flow.difficulty = diff
        self.difficulty_selected.emit(diff)
