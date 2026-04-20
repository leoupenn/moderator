"""Character carousel — 5 duck variants with left/right arrows and name pill."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...session.flow_state import Character
from .asset_loader import asset_path
from .duck_mascot import DuckMascot


_ROW_SPECS: List[tuple[Character, int, int]] = [
    (Character.BABY_DUCK, 55, 61),
    (Character.YOUNG_DUCK, 95, 105),
    (Character.NORMAL_DUCK, 239, 263),
    (Character.COOL_DUCK, 95, 105),
    (Character.SPY_DUCK, 55, 61),
]


class CharacterStrip(QFrame):
    """Blue rounded card containing the duck lineup and selection controls."""

    selection_changed = Signal(object)  # Character

    def __init__(
        self,
        player_label: str = "Player 1",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardBlue")
        self.setFixedSize(648, 530)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 28, 20, 28)
        outer.setSpacing(40)

        title = QLabel(player_label)
        title.setObjectName("PlayerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        ducks_row = QHBoxLayout()
        ducks_row.setContentsMargins(0, 0, 0, 0)
        ducks_row.setSpacing(18)
        ducks_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for char, w, h in _ROW_SPECS:
            d = DuckMascot(char.asset, w, h)
            ducks_row.addWidget(d, 0, Qt.AlignmentFlag.AlignBottom)
        ducks_host = QWidget()
        ducks_host.setLayout(ducks_row)
        outer.addWidget(ducks_host, 0, Qt.AlignmentFlag.AlignCenter)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(50)
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._prev = self._make_arrow(mirror=False)
        self._prev.clicked.connect(self._go_prev)
        controls.addWidget(self._prev)

        self._name = QLabel()
        self._name.setObjectName("CharNamePill")
        self._name.setFixedSize(247, 65)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self._name)

        self._next = self._make_arrow(mirror=True)
        self._next.clicked.connect(self._go_next)
        controls.addWidget(self._next)

        controls_host = QWidget()
        controls_host.setLayout(controls)
        outer.addWidget(controls_host, 0, Qt.AlignmentFlag.AlignCenter)

        self._order = [c for c, _, _ in _ROW_SPECS]
        self._idx = 2  # default to Normal Duck
        self._update_name()

    @staticmethod
    def _make_arrow(mirror: bool) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("ArrowChip")
        btn.setFixedSize(40, 40)
        icon = QIcon(str(asset_path("expand_left.svg")))
        btn.setIcon(icon)
        btn.setIconSize(QSize(24, 24))
        if mirror:
            btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            btn.setStyleSheet("QPushButton#ArrowChip { qproperty-layoutDirection: RightToLeft; }")
        return btn

    def _go_prev(self) -> None:
        self._idx = (self._idx - 1) % len(self._order)
        self._update_name()
        self.selection_changed.emit(self.current())

    def _go_next(self) -> None:
        self._idx = (self._idx + 1) % len(self._order)
        self._update_name()
        self.selection_changed.emit(self.current())

    def current(self) -> Character:
        return self._order[self._idx]

    def set_current(self, character: Character) -> None:
        try:
            self._idx = self._order.index(character)
        except ValueError:
            return
        self._update_name()

    def _update_name(self) -> None:
        self._name.setText(self._order[self._idx].label)
