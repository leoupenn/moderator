"""Figma 21:1520 / 45:847 — 'Choose # of Rounds' (5 / 10 / Custom).

Multiplayer behavior:
- Host drives the selection. Every click updates ``flow.rounds_total`` and
  triggers a ``MSG_STATE`` rebroadcast so the client sees the same card
  check on its own screen.
- Client renders the identical layout but with the buttons disabled and
  the Confirm button hidden; the subtitle switches to a "host is choosing"
  hint so the player knows the wait is intentional.
"""
from __future__ import annotations

from typing import List, Tuple

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

from ...session import FlowState, NetworkRole
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage


_PRESETS: List[Tuple[str, int]] = [
    ("5 Rounds", 5),
    ("10 Rounds", 10),
    ("Custom", -1),
]


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

        self._sub = QLabel("HOW LONG DO YOU WANT TO PLAY?", self)
        self._sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        self._sub.setFont(sf)
        self._sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._sub.adjustSize()
        self._sub.move(45, 169)

        host = QWidget(self)
        host.setGeometry(351, 281, 809, 470)

        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(40)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._custom_value = flow.rounds_total
        self._buttons: List[QPushButton] = []

        for label, value in _PRESETS:
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
            self._buttons.append(btn)

        self._group.buttonClicked.connect(self._on_clicked)

        self._confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        self._confirm.move((DESIGN_W - 334) // 2, 839)
        self._confirm.clicked.connect(self._on_confirm)

    # ----- lifecycle / mirroring -----------------------------------------
    def on_enter(self) -> None:
        self._apply_role_ui()
        self._sync_checked_from_flow()

    def apply_remote_selection(self) -> None:
        """Called from MainWindow after an inbound MSG_STATE refreshes flow."""
        self._sync_checked_from_flow()

    def _is_local_owner(self) -> bool:
        return self.flow.network_role != NetworkRole.CLIENT

    def _apply_role_ui(self) -> None:
        owner = self._is_local_owner()
        for btn in self._buttons:
            btn.setEnabled(owner)
        self._confirm.setVisible(owner)
        if owner:
            self._sub.setText("HOW LONG DO YOU WANT TO PLAY?")
        else:
            self._sub.setText("HOST IS CHOOSING\u2026")
        self._sub.adjustSize()

    def _sync_checked_from_flow(self) -> None:
        """Tick whichever preset matches ``flow.rounds_total`` (or Custom)."""
        rounds = int(self.flow.rounds_total)
        matched = False
        for btn in self._buttons:
            value = int(btn.property("rounds_value"))
            if value == rounds:
                btn.setChecked(True)
                matched = True
                break
        if not matched:
            self._custom_value = rounds
            custom_btn = self._buttons[-1]
            custom_btn.setText(f"Custom \u2014 {rounds} Rounds")
            custom_btn.setChecked(True)

    # ----- host interaction ----------------------------------------------
    def _on_clicked(self, btn: QPushButton) -> None:
        if not self._is_local_owner():
            return
        value = int(btn.property("rounds_value"))
        if value == -1:
            current = self._custom_value if self._custom_value > 0 else 5
            val, ok = QInputDialog.getInt(
                self, "Custom Rounds", "Number of rounds", current, 1, 50
            )
            if ok:
                self._custom_value = val
                btn.setText(f"Custom \u2014 {val} Rounds")
                self.flow.rounds_total = val
            else:
                btn.setChecked(False)
                return
        else:
            self.flow.rounds_total = value
        self._publish_selection()

    def _publish_selection(self) -> None:
        mw = self._main_window()
        if mw is None:
            return
        broadcast = getattr(mw, "broadcast_state", None)
        if callable(broadcast):
            broadcast()

    def _on_confirm(self) -> None:
        if not self._is_local_owner():
            return
        btn = self._group.checkedButton()
        if btn is None:
            return
        value = int(btn.property("rounds_value"))
        rounds = self._custom_value if value == -1 else value
        self.flow.rounds_total = rounds
        self.flow.reset_match()
        self.confirmed.emit(rounds)
