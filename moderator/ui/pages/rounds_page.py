"""Figma 21:1520 / 45:847 — 'Choose # of Rounds' (5 / 10 / Custom)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...session import FlowState
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage


class RoundsPage(FlowPage):
    confirmed = Signal(int)  # rounds_total

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("CHOOSE # OF ROUNDS", self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(45, 32)

        sub = QLabel("HOW LONG DO YOU WANT TO PLAY?", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(45, 169)

        host = QWidget(self)
        host.setGeometry(351, 281, 809, 470)

        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(40)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._custom_value = flow.rounds_total

        for label, value in (("5 Rounds", 5), ("10 Rounds", 10), ("Custom", -1)):
            btn = QPushButton(label, host)
            btn.setObjectName("RoundsCard")
            btn.setCheckable(True)
            btn.setFixedHeight(128)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            f = QFont(THEME.font_display)
            f.setPixelSize(52)
            btn.setFont(f)
            btn.setProperty("rounds_value", value)
            col.addWidget(btn)
            self._group.addButton(btn)

        self._group.buttonClicked.connect(self._on_clicked)

        confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        confirm.move((DESIGN_W - 334) // 2, 839)
        confirm.clicked.connect(self._on_confirm)

    def _on_clicked(self, btn: QPushButton) -> None:
        if btn.property("rounds_value") == -1:
            val, ok = QInputDialog.getInt(
                self, "Custom Rounds", "Number of rounds", self._custom_value, 1, 50
            )
            if ok:
                self._custom_value = val
                btn.setText(f"Custom — {val} Rounds")
            else:
                btn.setChecked(False)

    def _on_confirm(self) -> None:
        btn = self._group.checkedButton()
        if btn is None:
            return
        value = btn.property("rounds_value")
        rounds = self._custom_value if value == -1 else int(value)
        self.flow.rounds_total = rounds
        self.flow.reset_match()
        self.confirmed.emit(rounds)
