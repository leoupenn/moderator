"""Hero header — kicker (small) + huge Jersey-10 title + optional subtitle."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..theme import THEME


class PageHeader(QWidget):
    """Figma hero stack: kicker (optional), huge title, subtitle (optional)."""

    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        kicker: Optional[str] = None,
        title_size: int = 96,
        subtitle_size: int = 36,
        align_left: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        align = Qt.AlignmentFlag.AlignLeft if align_left else Qt.AlignmentFlag.AlignCenter

        if kicker:
            k = QLabel(kicker.upper())
            k.setObjectName("Kicker")
            k.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            col.addWidget(k)

        self._title = QLabel(title.upper())
        self._title.setObjectName("HeroTitle")
        font = QFont(THEME.font_display)
        font.setPixelSize(title_size)
        self._title.setFont(font)
        self._title.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self._title.setWordWrap(False)
        col.addWidget(self._title)

        self._subtitle: Optional[QLabel] = None
        if subtitle:
            s = QLabel(subtitle.upper())
            s.setObjectName("HeroSubtitle")
            sf = QFont(THEME.font_display)
            sf.setPixelSize(subtitle_size)
            s.setFont(sf)
            s.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            col.addWidget(s)
            self._subtitle = s

    def set_title(self, text: str) -> None:
        self._title.setText(text.upper())

    def set_subtitle(self, text: str) -> None:
        if self._subtitle is not None:
            self._subtitle.setText(text.upper())
