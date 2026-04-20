"""Figma 21:2139 — Single Player 'Choose Your Genre' (2×5 grid of genre cards)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QLabel, QPushButton, QWidget

from ...session import FlowState, Genre
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage


_GRID = [
    [Genre.JAZZ, Genre.POP, Genre.KPOP, Genre.JPOP, Genre.CLASSIC],
    [Genre.SIMPLE, Genre.TECHNO, Genre.BLUES, Genre.SALSA, Genre.FUNK],
]


class SinglePlayerGenrePage(FlowPage):
    confirmed = Signal(object)  # Genre

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("CHOOSE YOUR GENRE", self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(45, 32)

        sub = QLabel("WHAT MUSIC DO YOU LIKE?", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(45, 169)

        host = QWidget(self)
        host.setGeometry(107, 332, 5 * 234 + 4 * 30, 2 * 190 + 30)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(30)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for r, row in enumerate(_GRID):
            for c, genre in enumerate(row):
                btn = QPushButton(genre.value, host)
                btn.setObjectName("GenreCard")
                btn.setCheckable(True)
                btn.setFixedSize(234, 190)
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                gf = QFont(THEME.font_display)
                gf.setPixelSize(54)
                btn.setFont(gf)
                btn.setProperty("genre_name", genre.name)
                grid.addWidget(btn, r, c)
                self._group.addButton(btn)

        confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        confirm.move((DESIGN_W - 334) // 2, 861)
        confirm.clicked.connect(self._on_confirm)

    def on_enter(self) -> None:
        if self.flow.genre is not None:
            for btn in self._group.buttons():
                if btn.property("genre_name") == self.flow.genre.name:
                    btn.setChecked(True)
                    break

    def _on_confirm(self) -> None:
        btn = self._group.checkedButton()
        if btn is None:
            return
        genre = Genre[btn.property("genre_name")]
        self.flow.genre = genre
        self.confirmed.emit(genre)
