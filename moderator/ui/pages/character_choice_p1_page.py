"""Figma 21:606 — Competition Character Choice (Player 1 view).

Multiplayer behavior:
- On the host (``local_player == 1``) this is the interactive picker.
- On the client (``local_player == 2``) it renders as a read-only preview of
  whichever duck Player 1 is currently hovering on the host; the strip is
  locked and Confirm is hidden. The host drives advancement.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from ...net import MSG_CHARACTER_SELECT
from ...session import FlowState, NetworkRole
from ..theme import DESIGN_W, THEME
from ..widgets import CharacterStrip, ChoiceButton, ChoiceStyle, FlowPage


class CharacterChoiceP1Page(FlowPage):
    confirmed = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        title = QLabel("CHOOSE YOUR CHARACTER", self)
        title.setObjectName("HeroTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(THEME.size_display_hero)
        title.setFont(tf)
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title.adjustSize()
        title.move(45, 32)

        self._sub = QLabel("WHAT DUCK WOULD YOU LIKE?", self)
        self._sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        self._sub.setFont(sf)
        self._sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._sub.adjustSize()
        self._sub.move(45, 169)

        self._strip = CharacterStrip("Player 1", self)
        self._strip.move((DESIGN_W - 648) // 2, 271)
        self._strip.set_current(flow.character_p1)
        self._strip.selection_changed.connect(self._on_strip_changed)

        self._confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        self._confirm.move((DESIGN_W - 334) // 2, 858)
        self._confirm.clicked.connect(self._on_confirm)

    def on_enter(self) -> None:
        self._strip.set_current(self.flow.character_p1)
        self._apply_role_ui()

    # ----- role-aware UI -------------------------------------------------
    def _is_local_owner(self) -> bool:
        """True when the local machine is allowed to drive this picker."""
        return self.flow.network_role != NetworkRole.CLIENT

    def _apply_role_ui(self) -> None:
        owner = self._is_local_owner()
        self._set_strip_enabled(owner)
        self._confirm.setVisible(owner)
        if owner:
            self._sub.setText("WHAT DUCK WOULD YOU LIKE?")
        else:
            self._sub.setText("PLAYER 1 IS CHOOSING\u2026")
        self._sub.adjustSize()

    def _set_strip_enabled(self, enabled: bool) -> None:
        # Lock the left/right arrows without restyling the whole card —
        # the preview still needs to render the currently-picked duck.
        try:
            self._strip._prev.setEnabled(enabled)  # noqa: SLF001
            self._strip._next.setEnabled(enabled)  # noqa: SLF001
        except AttributeError:
            pass

    # ----- selection wiring ---------------------------------------------
    def _on_strip_changed(self, character) -> None:
        if not self._is_local_owner():
            return
        self.flow.character_p1 = character
        mw = self._main_window()
        if mw is None:
            return
        role = self.flow.network_role
        if role == NetworkRole.HOST:
            mw.net.send(
                MSG_CHARACTER_SELECT,
                player=1,
                character=character.name,
            )

    def _on_confirm(self) -> None:
        if not self._is_local_owner():
            return
        self.flow.character_p1 = self._strip.current()
        self.confirmed.emit()

    # ----- remote updates ------------------------------------------------
    def apply_remote_selection(self) -> None:
        """MainWindow calls this when an inbound character_select lands."""
        self._strip.set_current(self.flow.character_p1)

    # ----- helpers -------------------------------------------------------
    def _main_window(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
