"""Figma 21:2404 — Loading splash.

"LOADING..." + mascot duck + decorative line. Auto-advances to the next route
after ``AUTO_ADVANCE_MS``. All coordinates come straight from Figma.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...session import FlowState
from ..theme import THEME
from ..widgets import FlowPage
from ..widgets.asset_loader import svg_widget


class LoadingPage(FlowPage):
    """Splash screen; emits ``finished`` when auto-advance expires."""

    finished = Signal()

    AUTO_ADVANCE_MS = 1800

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("LOADING...", self)
        title.setObjectName("HeroTitle")
        f = QFont(THEME.font_display)
        f.setPixelSize(THEME.size_display_hero)
        title.setFont(f)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(554, 342)

        duck = svg_widget("duck_loading.svg", 110, 121, self)
        duck.move(410, 519)

        line = svg_widget("loading_line.svg", 807, 12, self)
        line.move(353, 651)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.finished.emit)

    def on_enter(self) -> None:
        self._timer.start(self.AUTO_ADVANCE_MS)
