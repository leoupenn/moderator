"""Pill-shaped choice buttons used across selection screens (334×91, Figma)."""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QPushButton, QWidget

from ..theme import THEME


class ChoiceStyle(Enum):
    BLUE = "ChoiceBlue"
    YELLOW = "ChoiceYellow"
    DARK = "ChoiceDark"


class ChoiceButton(QPushButton):
    """Jersey-10 48px label; 334×91 pill; blue / yellow / dark variants."""

    def __init__(
        self,
        text: str,
        style: ChoiceStyle = ChoiceStyle.BLUE,
        width: int = 334,
        height: int = 91,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName(style.value)
        self.setFixedSize(width, height)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        font = QFont(THEME.font_display)
        font.setPixelSize(44)
        self.setFont(font)
