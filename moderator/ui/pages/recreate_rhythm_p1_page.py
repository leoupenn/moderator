"""Figma 21:901 — Recreate Rhythm P1 ('Make a Rhythm!', BPM pill, submit).

Role-aware rendering:

* **Host / Solo**: the authoritative P1 (the host is always Player 1) sees
  the full interactive layout — BPM pill, Submit/Preview buttons, keyboard
  shortcuts (D submits, Space previews). When P1 submits we also broadcast
  ``MSG_RR_TARGET`` so the joining machine can grade the recreation against
  the same reference pattern.
* **Client (Player 2)**: sees a passive "Player 1 is creating a rhythm…"
  waiting screen with their own duck. All interactive controls (BPM,
  Submit, Preview, key handlers) are hidden/ignored while P1 is composing.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...net import MSG_RR_TARGET
from ...session import FlowState, GameSession, NetworkRole
from ..theme import DESIGN_W, THEME
from ..widgets import (
    BpmInput,
    ChoiceButton,
    ChoiceStyle,
    DuckMascot,
    FlowPage,
    RhythmTrackGrid,
)


class RecreateRhythmP1Page(FlowPage):
    submitted = Signal()

    def __init__(
        self,
        flow: FlowState,
        session: GameSession,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(flow, parent)
        self._session = session

        kicker = QLabel("COMPETITIVE MODE", self)
        kicker.setObjectName("HeroTitleSm")
        kf = QFont(THEME.font_display)
        kf.setPixelSize(64)
        kicker.setFont(kf)
        kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        kicker.adjustSize()
        kicker.move(35, 32)

        sub = QLabel("Recreate Rhythms", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(40)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(35, 101)

        self._round_label = QLabel("ROUND 1", self)
        rf = QFont(THEME.font_display)
        rf.setPixelSize(32)
        self._round_label.setFont(rf)
        self._round_label.setObjectName("Kicker")
        self._round_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 220, 88)

        card = QFrame(self)
        card.setObjectName("CardBlue")
        card.setGeometry(352, 266, 866, 520)

        col = QVBoxLayout(card)
        col.setContentsMargins(48, 28, 48, 48)
        col.setSpacing(22)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._player_title = QLabel("Player 1", card)
        self._player_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        self._player_title.setFont(pf)
        self._player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._player_title)

        self._hero = QLabel("Make a Rhythm!", card)
        self._hero.setObjectName("TimeDigits")
        hf = QFont(THEME.font_display)
        hf.setPixelSize(96)
        self._hero.setFont(hf)
        self._hero.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._hero)

        self._bpm = BpmInput(flow.bpm, card)
        col.addWidget(self._bpm, 0, Qt.AlignmentFlag.AlignHCenter)
        self._bpm.value_changed.connect(self._on_bpm)

        self._hint = QLabel("Press D to submit", card)
        self._hint.setObjectName("SubmitHint")
        hf2 = QFont(THEME.font_display)
        hf2.setPixelSize(36)
        self._hint.setFont(hf2)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._hint)

        self._track = RhythmTrackGrid(self)
        self._track.move(221, 800)
        self._track.setVisible(False)

        self._duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        self._duck.move(293, 218)

        self._submit_btn = ChoiceButton(
            "Submit", ChoiceStyle.DARK, width=220, height=64, parent=self
        )
        tbf = QFont(THEME.font_display)
        tbf.setPixelSize(28)
        self._submit_btn.setFont(tbf)
        self._submit_btn.move((DESIGN_W - 220) // 2 + 150, 800)
        self._submit_btn.clicked.connect(self._submit)

        self._preview_btn = ChoiceButton(
            "Preview", ChoiceStyle.BLUE, width=220, height=64, parent=self
        )
        self._preview_btn.setFont(tbf)
        self._preview_btn.move((DESIGN_W - 220) // 2 - 150, 800)
        self._preview_btn.clicked.connect(session.play_current)

        session.live_pattern_changed.connect(self._on_live)
        session.status_changed.connect(self._on_status)

        self._status = QLabel("", self)
        self._status.setObjectName("StatusLine")
        self._status.setGeometry(35, 920, DESIGN_W - 70, 30)

    # ----- role detection --------------------------------------------------
    def _is_client_spectator(self) -> bool:
        return self.flow.network_role == NetworkRole.CLIENT

    # ----- lifecycle -------------------------------------------------------
    def on_enter(self) -> None:
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)

        if self._is_client_spectator():
            # Player 2's passive waiting view — same layout, neutered controls.
            self._player_title.setText("Player 2")
            self._hero.setText("Waiting for Player 1…")
            self._hint.setText("Player 1 is creating a rhythm")
            self._duck.set_asset(self.flow.character_p2.asset)
            self._bpm.setVisible(False)
            self._submit_btn.setVisible(False)
            self._preview_btn.setVisible(False)
            self._status.setText("")
        else:
            # Host / Solo: full interactive composer.
            self._player_title.setText("Player 1")
            self._hero.setText("Make a Rhythm!")
            self._hint.setText("Press D to submit")
            self._duck.set_asset(self.flow.character_p1.asset)
            self._bpm.setVisible(True)
            self._submit_btn.setVisible(True)
            self._preview_btn.setVisible(True)
            self._session.start_new_match()
            self._session.set_bpm(self.flow.bpm)
            self._bpm.set_value(self.flow.bpm)
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ----- host interactions -----------------------------------------------
    def _on_bpm(self, v: int) -> None:
        if self._is_client_spectator():
            return
        self.flow.bpm = int(v)
        self._session.set_bpm(self.flow.bpm)

    def _on_live(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)

    def _on_status(self, msg: str) -> None:
        if self._is_client_spectator():
            return
        self._status.setText(msg)

    def _submit(self) -> None:
        if self._is_client_spectator():
            return
        ok = self._session.p1_submit()
        if not ok:
            self._status.setText("Rhythm pad reading not stable yet — hold still and retry.")
            return
        # Fire nav first (the MainWindow listener calls nav.go("rr_p2") which
        # broadcasts MSG_NAV); then send the authoritative reference pattern
        # so the client's rr_p2 page has it ready before it needs to grade.
        self.submitted.emit()
        if self.flow.network_role == NetworkRole.HOST:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_RR_TARGET,
                    pattern=list(self._session.p1_pattern),
                    bpm=int(self.flow.bpm),
                    round=int(self.flow.current_round),
                )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._is_client_spectator():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_D:
            self._submit()
        elif event.key() == Qt.Key.Key_Space:
            self._session.play_current()
        else:
            super().keyPressEvent(event)

    # ----- helpers ---------------------------------------------------------
    def _main_window(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
