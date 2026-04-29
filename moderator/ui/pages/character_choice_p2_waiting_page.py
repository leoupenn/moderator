"""Figma 29:808 — 'Waiting for other player…' with P2 character pick underneath.

Multiplayer behavior:
- Client (``local_player == 2``) owns the picker: arrows active, Confirm
  sends ``MSG_READY`` to the host instead of advancing locally. The host
  then navigates to ``rounds`` which the client mirrors over ``MSG_NAV``.
- Host (``local_player == 1``) sees a read-only preview of whichever duck
  the client is hovering, plus a "Player 2 is choosing\u2026" banner. Confirm
  is hidden.
- Solo matches keep today's behavior: same machine picks, overlay shows,
  ``confirmed`` is emitted after the short delay.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...net import MSG_CHARACTER_SELECT, MSG_READY
from ...session import FlowState, NetworkRole
from ..theme import DESIGN_W, THEME
from ..widgets import CharacterStrip, ChoiceButton, ChoiceStyle, FlowPage


class CharacterChoiceP2WaitingPage(FlowPage):
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

        self._sub = QLabel("PLAYER 2 \u2014 PICK YOUR DUCK", self)
        self._sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_2)
        self._sub.setFont(sf)
        self._sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._sub.adjustSize()
        self._sub.move(45, 169)

        self._strip = CharacterStrip("Player 2", self, card_style="CardYellow")
        self._strip.move((DESIGN_W - 648) // 2, 271)
        self._strip.set_current(flow.character_p2)
        self._strip.selection_changed.connect(self._on_strip_changed)

        self._confirm = ChoiceButton("Confirm", ChoiceStyle.DARK, parent=self)
        self._confirm.move((DESIGN_W - 334) // 2, 858)
        self._confirm.clicked.connect(self._on_confirm)

        self._overlay = self._build_overlay()
        self._overlay.hide()

    def on_enter(self) -> None:
        self._strip.set_current(self.flow.character_p2)
        self._overlay.hide()
        self._apply_role_ui()

    # ----- role-aware UI -------------------------------------------------
    def _is_local_owner(self) -> bool:
        return self.flow.network_role != NetworkRole.HOST

    def _apply_role_ui(self) -> None:
        owner = self._is_local_owner()
        try:
            self._strip._prev.setEnabled(owner)  # noqa: SLF001
            self._strip._next.setEnabled(owner)  # noqa: SLF001
        except AttributeError:
            pass
        self._confirm.setVisible(owner)
        if owner:
            self._sub.setText("PLAYER 2 \u2014 PICK YOUR DUCK")
        else:
            self._sub.setText("PLAYER 2 IS CHOOSING\u2026")
        self._sub.adjustSize()

    # ----- selection wiring ---------------------------------------------
    def _on_strip_changed(self, character) -> None:
        if not self._is_local_owner():
            return
        self.flow.character_p2 = character
        mw = self._main_window()
        if mw is None:
            return
        role = self.flow.network_role
        if role == NetworkRole.CLIENT:
            mw.net.send(
                MSG_CHARACTER_SELECT,
                player=2,
                character=character.name,
            )

    def _on_confirm(self) -> None:
        if not self._is_local_owner():
            return
        self.flow.character_p2 = self._strip.current()
        role = self.flow.network_role
        mw = self._main_window()
        if role == NetworkRole.CLIENT and mw is not None:
            # Let the host know we're ready; host will broadcast the nav
            # transition to rounds so both machines advance together. No
            # local overlay — the "Ready!" splash happens on the host side
            # as part of its normal flow.
            mw.net.send(MSG_READY, from_player=2, screen="char_p2")
            return
        # Solo (or the rare case where a host also operates the P2 pick):
        # reproduce today's overlay + auto-advance behavior.
        self._overlay.show()
        self._overlay.raise_()
        QTimer.singleShot(1100, self._finish)

    def _finish(self) -> None:
        self._overlay.hide()
        self.confirmed.emit()

    # ----- remote updates ------------------------------------------------
    def apply_remote_selection(self) -> None:
        """MainWindow calls this when an inbound character_select lands."""
        self._strip.set_current(self.flow.character_p2, animate=True)

    # ----- overlay -------------------------------------------------------
    def _build_overlay(self) -> QFrame:
        scrim = QFrame(self)
        scrim.setObjectName("Scrim")
        scrim.setGeometry(0, 0, DESIGN_W, self.height())

        modal = QFrame(scrim)
        modal.setObjectName("WaitingModal")
        modal.setFixedSize(730, 300)
        modal.move((DESIGN_W - 730) // 2, (self.height() - 300) // 2)

        col = QVBoxLayout(modal)
        col.setContentsMargins(60, 40, 60, 40)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Ready!", modal)
        label.setObjectName("WaitingTitle")
        f = QFont(THEME.font_display)
        f.setPixelSize(96)
        label.setFont(f)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(label)

        sub = QLabel("Let the match begin\u2026", modal)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(36)
        sub.setFont(sf)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(sub)
        return scrim
