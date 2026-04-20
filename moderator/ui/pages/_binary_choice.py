"""Helper for the Tutorial / SP-Experience / Competition pages, which share layout.

Figma frames 8:58, 17:242, 17:272 are identical except for the title/subtitle
and button labels: two 334×91 pills side-by-side below a huge Jersey-10 title.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...session import FlowState
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage
from ..widgets.asset_loader import svg_widget


class BinaryChoicePage(FlowPage):
    """Title + subtitle + two pill buttons (blue left, yellow right)."""

    def __init__(
        self,
        flow: FlowState,
        title: str,
        subtitle: str,
        left_label: str,
        right_label: str,
        parent: QWidget | None = None,
        kicker: str | None = None,
        show_decorations: bool = True,
    ) -> None:
        super().__init__(flow, parent)

        self._kicker_lbl: QLabel | None = None
        if kicker:
            k = QLabel(kicker.upper(), self)
            k.setObjectName("Kicker")
            kf = QFont(THEME.font_display)
            kf.setPixelSize(28)
            k.setFont(kf)
            k.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            k.adjustSize()
            k.move(63, 130)
            self._kicker_lbl = k

        self._title = QLabel(title.upper(), self)
        self._title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        self._title.setFont(tf)
        self._title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._title.adjustSize()
        self._title.move((DESIGN_W - self._title.width()) // 2, 342)

        self._subtitle = QLabel(subtitle.upper(), self)
        self._subtitle.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        self._subtitle.setFont(sf)
        self._subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._subtitle.adjustSize()
        self._subtitle.move((DESIGN_W - self._subtitle.width()) // 2, 525)

        self._left = ChoiceButton(left_label, ChoiceStyle.BLUE, parent=self)
        self._left.move(349, 695)

        self._right = ChoiceButton(right_label, ChoiceStyle.YELLOW, parent=self)
        self._right.move(821, 695)

        if show_decorations:
            # Decorative checkmark + duck matching Figma 8:58 and 17:242.
            duck1 = svg_widget("group2_checkmark.svg", 64, 66, self)
            duck1.move(604, 649)
            duck2 = svg_widget("duck_med.svg", 67, 74, self)
            duck2.move(1088, 641)

    def connect_left(self, handler: Callable[[], None]) -> None:
        self._left.clicked.connect(handler)

    def connect_right(self, handler: Callable[[], None]) -> None:
        self._right.clicked.connect(handler)

    def set_title_text(self, text: str) -> None:
        self._title.setText(text.upper())
        self._title.adjustSize()
        self._title.move((DESIGN_W - self._title.width()) // 2, 342)

    def set_subtitle_text(self, text: str) -> None:
        self._subtitle.setText(text.upper())
        self._subtitle.adjustSize()
        self._subtitle.move((DESIGN_W - self._subtitle.width()) // 2, 525)
