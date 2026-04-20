"""Figma 6:21 — Welcome Page (home + mode-select).

Layout matches the Figma frame `Welcome Page` at 1512x982 exactly. Coordinates
are taken straight from `get_design_context` output; do not drift from them.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...session import FlowState, GameMode
from ..theme import THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage
from ..widgets.asset_loader import svg_widget


class WelcomePage(FlowPage):
    """Home screen that also serves as the Single/Multi mode picker."""

    mode_selected = Signal(object)  # GameMode

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        staff = svg_widget("notation_lines.svg", 294, 40, self)
        staff.move(610, 326)

        for x in (632, 704, 776, 848):
            duck = svg_widget("duck_small.svg", 50, 55, self)
            duck.move(x, 310)

        title = QLabel("BEAT IT!", self)
        title.setObjectName("HeroTitle")
        f = QFont(THEME.font_display)
        f.setPixelSize(THEME.size_display_hero)
        title.setFont(f)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(595, 365)

        for x in (610, 949, 1016):
            d = svg_widget("duck_med.svg", 67, 74, self)
            d.move(x, 641)

        single = ChoiceButton("Single Player", ChoiceStyle.BLUE, parent=self)
        single.adjustSize()
        single.move(370, 695)
        single.clicked.connect(lambda: self._emit(GameMode.SINGLE))

        multi = ChoiceButton("Multiplayer", ChoiceStyle.YELLOW, parent=self)
        multi.setFixedWidth(334)
        multi.move(791, 695)
        multi.clicked.connect(lambda: self._emit(GameMode.MULTI))

    def _emit(self, mode: GameMode) -> None:
        self.flow.mode = mode
        self.mode_selected.emit(mode)
