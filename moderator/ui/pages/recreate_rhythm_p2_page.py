"""Figma 21:944 / 30:995 / 30:1027 \u2014 Recreate Rhythm 'recreate' screen.

Players swap composer / recreator duties every round (see
``rr_recreator_player``):

* **Local recreator**: full interactive page \u2014 the pad drives a fresh
  pattern, ``K`` / ``Return`` submits, ``Space`` replays the composer's
  rhythm. Grading is local against the pattern seeded by ``MSG_RR_TARGET``
  (or by ``GameSession.p1_submit`` on the host when the host composed).
  Every submit emits ``MSG_RR_ATTEMPT`` so the spectator mirror updates;
  the final ``MSG_RR_RESULT`` tells the peer the round is over.
* **Local spectator**: passive mirror. Strip click, submit and keys are
  disabled so the composer can't grade for the other player. The timer
  ticks locally for smoothness and re-anchors to every authoritative
  ``elapsed_ms`` the recreator sends us.

The **host is always authoritative for scoring + navigation**. When the
host is the recreator it records the ``RoundScore`` locally. When the
client is the recreator it sends ``MSG_RR_RESULT`` and the host records +
navigates to the results page.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...game_logic import (
    Phase,
    SLOTS,
    binary_pattern_for_playback,
)
from ...net import MSG_RR_ATTEMPT, MSG_RR_RESULT
from ...session import FlowState, GameSession, NetworkRole
from ...session.flow_state import (
    RoundScore,
    rr_composer_player,
    rr_recreator_player,
)
from ..theme import DESIGN_W, THEME
from ..widgets import (
    DuckMascot,
    FlowPage,
    RhythmTrackGrid,
)
from ..widgets.asset_loader import svg_widget


def _format_ms(ms: int) -> str:
    total_s = ms // 1000
    m = total_s // 60
    s = total_s % 60
    cs = (ms % 1000) // 10
    return f"{m:02d}:{s:02d}:{cs:02d}"


class RecreateRhythmP2Page(FlowPage):
    round_done = Signal()

    def __init__(
        self,
        flow: FlowState,
        session: GameSession,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(flow, parent)
        self._session = session
        self._match_start: Optional[float] = None
        self._attempts = 1
        self._elapsed_ms = 0
        self._finished = False
        self._target: Optional[List[int]] = None

        kicker = QLabel("COMPETITIVE MODE", self)
        kf = QFont(THEME.font_display)
        kf.setPixelSize(64)
        kicker.setFont(kf)
        kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        kicker.adjustSize()
        kicker.move(35, 32)

        sub = QLabel("Recreate Rhythm", self)
        sf = QFont(THEME.font_display)
        sf.setPixelSize(40)
        sub.setFont(sf)
        sub.setObjectName("HeroSubtitle")
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(35, 101)

        self._round_label = QLabel("ROUND 1", self)
        rf = QFont(THEME.font_display)
        rf.setPixelSize(32)
        self._round_label.setFont(rf)
        self._round_label.setObjectName("Kicker")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 220, 88)

        self._strip = QFrame(self)
        self._strip.setObjectName("RhythmStrip")
        self._strip.setGeometry(213, 172, 1086, 95)
        self._strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._strip_lbl = QLabel("Play Player 1's Rhythm\u2026", self._strip)
        self._strip_lbl.setObjectName("StripLabel")
        sl = QFont(THEME.font_display)
        sl.setPixelSize(36)
        self._strip_lbl.setFont(sl)
        self._strip_lbl.adjustSize()
        self._strip_lbl.move(50, 28)

        self._play_icon = svg_widget("play_ellipse.svg", 60, 60, self._strip)
        self._play_icon.move(1010, 18)
        self._strip.mousePressEvent = self._strip_clicked  # type: ignore[assignment]

        card = QFrame(self)
        card.setObjectName("CardYellow")
        card.setGeometry((DESIGN_W - 1067) // 2, 287, 1067, 357)

        col = QVBoxLayout(card)
        col.setContentsMargins(40, 24, 40, 24)
        col.setSpacing(18)

        self._player_title = QLabel("Player 2", card)
        self._player_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        self._player_title.setFont(pf)
        self._player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._player_title)

        self._time_lbl = QLabel("00:00:00", card)
        self._time_lbl.setObjectName("TimeDigitsBig")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(112)
        self._time_lbl.setFont(tf)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._time_lbl)

        self._attempt_lbl = QLabel("Attempt 1", card)
        af = QFont(THEME.font_display)
        af.setPixelSize(52)
        self._attempt_lbl.setFont(af)
        self._attempt_lbl.setObjectName("AttemptLabel")
        self._attempt_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._attempt_lbl)

        self._hint_lbl = QLabel("Press K to submit", card)
        self._hint_lbl.setObjectName("SubmitHint")
        hf = QFont(THEME.font_display)
        hf.setPixelSize(36)
        self._hint_lbl.setFont(hf)
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._hint_lbl)

        self._duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        self._duck.move(1217, 275)

        prev_label = QLabel("Previous Attempt", self)
        prev_label.setObjectName("HeroSubtitle")
        pfl = QFont(THEME.font_display)
        pfl.setPixelSize(32)
        prev_label.setFont(pfl)
        prev_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        prev_label.adjustSize()
        prev_label.move(229, 679)

        self._track = RhythmTrackGrid(self)
        self._track.move(229, 730)

        self._status = QLabel("", self)
        self._status.setObjectName("StatusLine")
        self._status.setGeometry(229, 921, DESIGN_W - 458, 22)

        session.live_pattern_changed.connect(self._on_live)
        session.feedback_ready.connect(self._on_feedback)
        session.round_won.connect(self._on_round_won)
        session.round_lost_reveal.connect(self._on_round_lost)
        session.phase_changed.connect(self._on_phase)
        session.status_changed.connect(self._on_status)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)

    # ----- role helpers ----------------------------------------------------
    def _composer_player(self) -> int:
        return rr_composer_player(self.flow.current_round)

    def _recreator_player(self) -> int:
        return rr_recreator_player(self.flow.current_round)

    def _is_local_recreator(self) -> bool:
        return self.flow.local_player == self._recreator_player()

    def _is_local_spectator(self) -> bool:
        return not self._is_local_recreator()

    def _recreator_character(self):
        return (
            self.flow.character_p1
            if self._recreator_player() == 1
            else self.flow.character_p2
        )

    # ----- lifecycle -------------------------------------------------------
    def on_enter(self) -> None:
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)
        self._attempts = 1
        self._elapsed_ms = 0
        self._finished = False
        self._attempt_lbl.setText("Attempt 1")
        self._time_lbl.setText(_format_ms(0))
        self._track.clear()
        self._status.setText("")

        rec = self._recreator_player()
        comp = self._composer_player()
        self._player_title.setText(f"Player {rec}")
        self._duck.set_asset(self._recreator_character().asset)

        if self._is_local_spectator():
            self._hint_lbl.setText(
                f"Player {rec} is recreating the rhythm\u2026"
            )
            self._strip_lbl.setText(
                f"Player {rec} is playing your rhythm"
            )
            self._play_icon.setVisible(False)
            self._strip.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self._hint_lbl.setText("Press K to submit")
            self._strip_lbl.setText(
                f"Play Player {comp}'s Rhythm\u2026"
            )
            self._play_icon.setVisible(True)
            self._strip.setCursor(Qt.CursorShape.PointingHandCursor)
            role = self.flow.network_role
            if role == NetworkRole.HOST:
                # On host-as-recreator the session's _p1_pattern was already
                # seeded by the MSG_RR_TARGET handler in MainWindow (or by
                # a local p1_submit in solo). Mirror it onto _target for the
                # replay button.
                self._target = list(self._session.p1_pattern)
            elif role == NetworkRole.CLIENT:
                # Client-as-recreator waits for MSG_RR_TARGET \u2014 submits are
                # gated until it arrives.
                self._target = None
            else:
                self._target = list(self._session.p1_pattern)

        self._match_start = time.monotonic()
        self._tick.start(50)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ----- strip click (Play composer's rhythm) ----------------------------
    def _strip_clicked(self, _e: QMouseEvent) -> None:
        if self._is_local_spectator():
            return
        self._session.play_reference()

    # ----- input -----------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._is_local_spectator():
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_K, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit()
        elif event.key() == Qt.Key.Key_Space:
            self._session.play_reference()
        else:
            super().keyPressEvent(event)

    # ----- tick / submit ---------------------------------------------------
    def _on_tick(self) -> None:
        if self._match_start is None or self._finished:
            return
        self._elapsed_ms = int((time.monotonic() - self._match_start) * 1000)
        self._time_lbl.setText(_format_ms(self._elapsed_ms))

    def _submit(self) -> None:
        if self._finished or self._is_local_spectator():
            return
        if self.flow.network_role == NetworkRole.CLIENT and self._target is None:
            self._status.setText("Waiting for Player {}'s rhythm\u2026".format(
                self._composer_player()
            ))
            return
        res = self._session.p2_submit()
        if res is None:
            self._status.setText("Rhythm pad reading not stable yet \u2014 hold still and retry.")
            return
        matches, n_ok = res
        attempt_pattern = binary_pattern_for_playback(self._session.live_state)
        if n_ok == SLOTS:
            self._broadcast_attempt(attempt_pattern, matches)
            self._finish(win=True, matches=matches)
            return
        self._attempts += 1
        self._attempt_lbl.setText(f"Attempt {self._attempts}")
        self._track.set_feedback(matches)
        self._broadcast_attempt(attempt_pattern, matches)
        QTimer.singleShot(900, self._session.feedback_continue)

    # ----- remote ingest (spectator mirror / target seed) ------------------
    def set_target(self, pattern: List[int], bpm: Optional[int] = None) -> None:
        """Seed the grading reference.

        Called on whichever machine is the recreator after the other side's
        ``MSG_RR_TARGET`` arrives (and on the host directly via the
        ``MSG_RR_TARGET`` handler when the client composed).
        """
        if not self._is_local_recreator():
            return
        self._target = list(pattern)
        self._session.set_manual_pattern(list(pattern))
        if isinstance(bpm, int) and bpm > 0:
            self._session.set_bpm(bpm)
        self._attempts = 1
        self._attempt_lbl.setText("Attempt 1")
        self._track.clear()

    def apply_remote_attempt(self, msg: dict) -> None:
        """Incoming ``MSG_RR_ATTEMPT`` \u2014 update the spectator card."""
        if not self._is_local_spectator() or self._finished:
            return
        try:
            attempts = int(msg.get("attempts", self._attempts))
            elapsed_ms = int(msg.get("elapsed_ms", self._elapsed_ms))
        except (TypeError, ValueError):
            return
        matches = msg.get("matches") or []
        self._attempts = max(1, attempts)
        self._attempt_lbl.setText(f"Attempt {self._attempts}")
        self._elapsed_ms = max(0, elapsed_ms)
        self._time_lbl.setText(_format_ms(self._elapsed_ms))
        # Re-anchor the spectator tick so the number keeps climbing smoothly
        # from the authoritative value instead of snapping backwards.
        self._match_start = time.monotonic() - (self._elapsed_ms / 1000.0)
        if isinstance(matches, list) and len(matches) == SLOTS:
            self._track.set_feedback([bool(v) for v in matches])

    def apply_remote_result(self, msg: dict) -> None:
        """Incoming ``MSG_RR_RESULT``.

        Behavior depends on the local role:

        * Host spectator (client was the recreator): record the
          authoritative ``RoundScore`` and navigate to results.
        * Client spectator (host was the recreator): refresh visuals only \u2014
          the host drives both the score and the ``MSG_NAV``.
        """
        if not self._is_local_spectator() or self._finished:
            return
        win = bool(msg.get("win", False))
        try:
            attempts = int(msg.get("attempts", self._attempts))
            elapsed_ms = int(msg.get("elapsed_ms", self._elapsed_ms))
        except (TypeError, ValueError):
            return
        self._finished = True
        self._tick.stop()
        self._attempts = max(1, attempts)
        self._attempt_lbl.setText(f"Attempt {self._attempts}")
        self._elapsed_ms = max(0, elapsed_ms)
        self._time_lbl.setText(_format_ms(self._elapsed_ms))
        if not win:
            self._track.set_feedback([False] * SLOTS)

        if self.flow.network_role == NetworkRole.HOST:
            self._record_score_for_round(win=win)
            QTimer.singleShot(1200, self.round_done.emit)

    # ----- result handling (local path) ------------------------------------
    def _finish(self, *, win: bool, matches: List[bool]) -> None:
        self._finished = True
        self._tick.stop()
        self._track.set_feedback(matches)
        self._broadcast_result(win=win)
        role = self.flow.network_role
        if role == NetworkRole.HOST or role == NetworkRole.SOLO:
            # Authoritative side records the score and drives nav.
            self._record_score_for_round(win=win)
            QTimer.singleShot(1200, self.round_done.emit)
        # Client recreator: host will append to flow.scores and broadcast
        # MSG_STATE + MSG_NAV. Nothing else to do locally.

    def _record_score_for_round(self, *, win: bool) -> None:
        """Append an authoritative ``RoundScore`` for this round.

        The recreator's player number owns ``attempts_p*`` and the elapsed
        time; the composer row is left at sensible defaults so the results
        card still renders cleanly for both players.
        """
        rec = self._recreator_player()
        winner = rec if win else self._composer_player()
        attempts_p1 = self._attempts if rec == 1 else 1
        attempts_p2 = self._attempts if rec == 2 else 1
        player1 = self._elapsed_ms if rec == 1 else 0
        player2 = self._elapsed_ms if rec == 2 else 0
        self.flow.scores.append(
            RoundScore(
                player1=player1,
                player2=player2,
                winner=winner,
                attempts_p1=attempts_p1,
                attempts_p2=attempts_p2,
            )
        )

    def _on_live(self, pattern: list) -> None:
        if self._is_local_spectator():
            return
        self._track.set_live_pattern(pattern)

    def _on_feedback(self, matches: list, _n_ok: int) -> None:
        if self._is_local_spectator():
            return
        self._track.set_feedback(matches)

    def _on_round_won(self) -> None:
        if self._is_local_spectator():
            return
        self._track.set_feedback([True] * SLOTS)

    def _on_round_lost(self, _reference: list) -> None:
        if self._is_local_spectator() or self._finished:
            return
        # MAX_FAILED_ATTEMPTS reached \u2014 composer wins this round.
        self._finished = True
        self._tick.stop()
        self._track.set_feedback([False] * SLOTS)
        self._broadcast_result(win=False)
        role = self.flow.network_role
        if role == NetworkRole.HOST or role == NetworkRole.SOLO:
            self._record_score_for_round(win=False)
            QTimer.singleShot(1200, self.round_done.emit)

    def _on_phase(self, _phase: Phase) -> None:
        pass

    def _on_status(self, msg: str) -> None:
        if self._is_local_spectator():
            return
        self._status.setText(msg)

    # ----- wire helpers ----------------------------------------------------
    def _broadcast_attempt(self, pattern: List[int], matches: List[bool]) -> None:
        if self.flow.network_role == NetworkRole.SOLO:
            return
        if not self._is_local_recreator():
            return
        mw = self._main_window()
        if mw is None:
            return
        mw.net.send(
            MSG_RR_ATTEMPT,
            pattern=list(pattern),
            matches=[bool(v) for v in matches],
            attempts=int(self._attempts),
            elapsed_ms=int(self._elapsed_ms),
        )

    def _broadcast_result(self, *, win: bool) -> None:
        if self.flow.network_role == NetworkRole.SOLO:
            return
        if not self._is_local_recreator():
            return
        mw = self._main_window()
        if mw is None:
            return
        mw.net.send(
            MSG_RR_RESULT,
            win=bool(win),
            attempts=int(self._attempts),
            elapsed_ms=int(self._elapsed_ms),
        )

    def _main_window(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
