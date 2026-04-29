"""Figma 21:901 — Recreate Rhythm 'compose' screen (used by both players).

Players swap composer / recreator duties every round:

* **Odd rounds** (1, 3, 5, \u2026): Player 1 (the host) composes, Player 2 recreates.
* **Even rounds** (2, 4, 6, \u2026): Player 2 (the client) composes, Player 1 recreates.

The page decides which machine owns the picker based on
``flow.local_player`` vs ``rr_composer_player(flow.current_round)``:

* **Local composer**: full interactive layout \u2014 BPM pill, Submit / Preview,
  ``D`` to submit, ``Space`` to preview. When they submit we broadcast
  ``MSG_RR_TARGET`` with the locked pattern so the peer grades against the
  same reference. Only the host actually navigates to ``rr_p2`` on its own
  machine; if the local composer is the client we just send the message
  and wait for the host's ``MSG_NAV`` to follow.
* **Local waiter**: passive \u2018\u2026is creating a rhythm\u2019 screen with their own
  duck. Controls are hidden, keys ignored.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...net import MSG_RR_TARGET
from ...phrase_audio import DEFAULT_COUNT_IN_QUARTERS
from ...session import FlowState, GameSession, NetworkRole
from ...session.flow_state import rr_composer_player
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

        self._card = QFrame(self)
        self._card.setObjectName("ComposerCard")
        self._card.setGeometry(352, 266, 866, 520)

        col = QVBoxLayout(self._card)
        col.setContentsMargins(48, 28, 48, 48)
        col.setSpacing(22)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._player_title = QLabel("Player 1", self._card)
        self._player_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        self._player_title.setFont(pf)
        self._player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._player_title)

        self._hero = QLabel("Make a Rhythm!", self._card)
        self._hero.setObjectName("TimeDigits")
        hf = QFont(THEME.font_display)
        hf.setPixelSize(96)
        self._hero.setFont(hf)
        self._hero.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._hero)

        self._bpm = BpmInput(flow.bpm, self._card)
        col.addWidget(self._bpm, 0, Qt.AlignmentFlag.AlignHCenter)
        self._bpm.value_changed.connect(self._on_bpm)

        self._hint = QLabel("Press D to submit", self._card)
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
        self._preview_btn.clicked.connect(self._preview_own_rhythm)

        session.live_pattern_changed.connect(self._on_live)
        session.status_changed.connect(self._on_status)

        self._status = QLabel("", self)
        self._status.setObjectName("StatusLine")
        self._status.setGeometry(35, 920, DESIGN_W - 70, 30)

        self._reminder_overlay = QFrame(self)
        self._reminder_overlay.setGeometry(0, 0, DESIGN_W, self.height())
        self._reminder_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._reminder_overlay.setStyleSheet(
            "QFrame { background: rgba(0, 0, 0, 128); border: none; }"
        )
        self._reminder_overlay.hide()
        self._reminder_overlay.mousePressEvent = self._dismiss_reminder  # type: ignore[assignment]

        reminder_card = QFrame(self._reminder_overlay)
        reminder_card.setGeometry(391, 294, 730, 396)
        reminder_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        reminder_card.setStyleSheet(
            "QFrame { background: white; border-radius: 20px; border: none; }"
        )

        reminder_inner = QVBoxLayout(reminder_card)
        reminder_inner.setContentsMargins(32, 40, 32, 40)
        reminder_inner.setSpacing(0)
        reminder_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        reminder_text = QLabel(
            "Make sure to\nremove the blocks\nto make your own\nrhythm!",
            reminder_card,
        )
        reminder_text.setObjectName("ReminderText")
        rtf = QFont(THEME.font_display)
        rtf.setPixelSize(64)
        # Wide lines + absolute letter spacing overflow a fixed 530px box when
        # centered; keep modest spacing so full card width fits comfortably.
        rtf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        reminder_text.setFont(rtf)
        reminder_text.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignVCenter
        )
        reminder_text.setWordWrap(True)
        reminder_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        reminder_text.setStyleSheet(
            f"color: {THEME.slate}; background: transparent; padding: 0 4px;"
        )
        reminder_inner.addWidget(reminder_text)
        self._reminder_visible = False

    # ----- role helpers ----------------------------------------------------
    def _composer_player(self) -> int:
        return rr_composer_player(self.flow.current_round)

    def _is_local_composer(self) -> bool:
        return self.flow.local_player == self._composer_player()

    def _composer_character(self):
        return (
            self.flow.character_p1
            if self._composer_player() == 1
            else self.flow.character_p2
        )

    # ----- lifecycle -------------------------------------------------------
    def on_enter(self) -> None:
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)

        composer = self._composer_player()
        self._player_title.setText(f"Player {composer}")
        card_bg = THEME.accent_yellow if composer == 2 else THEME.accent_blue
        self._card.setStyleSheet(
            "QFrame#ComposerCard {"
            f" background: {card_bg};"
            " border-radius: 20px;"
            " border: none;"
            "}"
        )

        if self._is_local_composer():
            # Local player owns the composer seat for this round.
            self._hero.setText("Make a Rhythm!")
            self._hint.setText("Press D to submit")
            self._duck.set_asset(self._composer_character().asset)
            self._bpm.setVisible(True)
            self._submit_btn.setVisible(True)
            self._preview_btn.setVisible(True)
            self._session.start_new_match()
            self._session.set_bpm(self.flow.bpm)
            self._bpm.set_value(self.flow.bpm)
            self._status.setText("")
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            if self.flow.current_round > 1:
                self._show_reminder()
            else:
                self._hide_reminder()
        else:
            # Remote player is composing; we render a passive wait screen.
            self._hero.setText("Waiting for Player {}\u2026".format(composer))
            self._hint.setText("Player {} is creating a rhythm".format(composer))
            self._duck.set_asset(self._composer_character().asset)
            self._bpm.setVisible(False)
            self._submit_btn.setVisible(False)
            self._preview_btn.setVisible(False)
            self._status.setText("")
            self._hide_reminder()

    # ----- interactive (composer) hooks -----------------------------------
    def _on_bpm(self, v: int) -> None:
        if not self._is_local_composer():
            return
        self.flow.bpm = int(v)
        self._session.set_bpm(self.flow.bpm)

    def _on_live(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)

    def _on_status(self, msg: str) -> None:
        if not self._is_local_composer():
            return
        self._status.setText(msg)

    def _preview_own_rhythm(self) -> None:
        """Preview live pad pattern; one measure count-in on each player's first compose turn (round 1 for P1, round 2 for P2)."""
        if self._reminder_visible:
            return
        if not self._is_local_composer():
            return
        composer = self._composer_player()
        first_compose_round = composer  # odd rounds: P1 from 1; even: P2 from 2
        n = DEFAULT_COUNT_IN_QUARTERS if self.flow.current_round == first_compose_round else 0
        self._session.play_current(count_in_quarters=n)

    def _submit(self) -> None:
        if self._reminder_visible:
            return
        if not self._is_local_composer():
            return
        ok = self._session.p1_submit()
        if not ok:
            self._status.setText("Rhythm pad reading not stable yet \u2014 hold still and retry.")
            return
        role = self.flow.network_role
        if role == NetworkRole.CLIENT:
            # Client-composer: don't navigate locally \u2014 push the target to the
            # host, which is authoritative for nav. Host will broadcast
            # MSG_NAV(rr_p2) which we'll follow.
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_RR_TARGET,
                    pattern=list(self._session.p1_pattern),
                    bpm=int(self.flow.bpm),
                    round=int(self.flow.current_round),
                )
            return
        # Host-composer or solo: navigate locally, then broadcast target.
        self.submitted.emit()
        if role == NetworkRole.HOST:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_RR_TARGET,
                    pattern=list(self._session.p1_pattern),
                    bpm=int(self.flow.bpm),
                    round=int(self.flow.current_round),
                )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._reminder_visible:
            self._hide_reminder()
            return
        if not self._is_local_composer():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_D:
            self._submit()
        elif event.key() == Qt.Key.Key_Space:
            self._preview_own_rhythm()
        else:
            super().keyPressEvent(event)

    def _show_reminder(self) -> None:
        self._reminder_visible = True
        self._reminder_overlay.show()
        self._reminder_overlay.raise_()
        # The Figma frame has no explicit button. Keep it transient, but allow
        # click/key dismissal so players can move on as soon as they are ready.
        QTimer.singleShot(3000, self._hide_reminder)

    def _hide_reminder(self) -> None:
        self._reminder_visible = False
        self._reminder_overlay.hide()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _dismiss_reminder(self, _event) -> None:
        self._hide_reminder()
