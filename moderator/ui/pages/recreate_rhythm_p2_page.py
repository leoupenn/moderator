"""Figma 21:944 / 30:995 / 30:1027 — Recreate Rhythm P2 view (recreation + feedback)."""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...game_logic import Phase, SLOTS
from ...session import FlowState, GameSession
from ...session.flow_state import RoundScore
from ..theme import DESIGN_W, THEME
from ..widgets import (
    ChoiceButton,
    ChoiceStyle,
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

        strip = QFrame(self)
        strip.setObjectName("RhythmStrip")
        strip.setGeometry(213, 172, 1086, 95)
        strip_lbl = QLabel("Play Player 1's Rhythm…", strip)
        strip_lbl.setObjectName("StripLabel")
        sl = QFont(THEME.font_display)
        sl.setPixelSize(36)
        strip_lbl.setFont(sl)
        strip_lbl.adjustSize()
        strip_lbl.move(50, 28)

        play_icon = svg_widget("play_ellipse.svg", 60, 60, strip)
        play_icon.move(1010, 18)

        card = QFrame(self)
        card.setObjectName("CardYellow")
        card.setGeometry((DESIGN_W - 1067) // 2, 287, 1067, 357)

        col = QVBoxLayout(card)
        col.setContentsMargins(40, 24, 40, 24)
        col.setSpacing(18)

        p2 = QLabel("Player 2", card)
        p2.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        p2.setFont(pf)
        p2.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(p2)

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

        play_btn = ChoiceButton("Play P1 rhythm", ChoiceStyle.BLUE, width=260, height=64, parent=self)
        pbf = QFont(THEME.font_display)
        pbf.setPixelSize(26)
        play_btn.setFont(pbf)
        play_btn.move(229, 940 - 70)
        play_btn.clicked.connect(session.play_reference)

        submit_btn = ChoiceButton("Submit", ChoiceStyle.DARK, width=260, height=64, parent=self)
        submit_btn.setFont(pbf)
        submit_btn.move(DESIGN_W - 229 - 260, 940 - 70)
        submit_btn.clicked.connect(self._submit)

        self._status = QLabel("", self)
        self._status.setObjectName("StatusLine")
        self._status.setGeometry(229, 945, DESIGN_W - 458, 24)

        session.live_pattern_changed.connect(self._on_live)
        session.feedback_ready.connect(self._on_feedback)
        session.round_won.connect(self._on_round_won)
        session.round_lost_reveal.connect(self._on_round_lost)
        session.phase_changed.connect(self._on_phase)
        session.status_changed.connect(self._on_status)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)

    # ----- lifecycle -------------------------------------------------------
    def on_enter(self) -> None:
        self._duck.set_asset(self.flow.character_p2.asset)
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)
        self._attempts = 1
        self._elapsed_ms = 0
        self._finished = False
        self._attempt_lbl.setText("Attempt 1")
        self._hint_lbl.setText("Press K to submit")
        self._time_lbl.setText(_format_ms(0))
        self._track.clear()
        self._match_start = time.monotonic()
        self._tick.start(50)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ----- input -----------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
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
        if self._finished:
            return
        res = self._session.p2_submit()
        if res is None:
            self._status.setText("Rhythm pad reading not stable yet — hold still and retry.")
            return
        matches, n_ok = res
        if n_ok == SLOTS:
            self._finish(win=True, matches=matches)
            return
        self._attempts += 1
        self._attempt_lbl.setText(f"Attempt {self._attempts}")
        self._track.set_feedback(matches)
        QTimer.singleShot(900, self._session.feedback_continue)

    # ----- result handling -------------------------------------------------
    def _finish(self, *, win: bool, matches: List[bool]) -> None:
        self._finished = True
        self._tick.stop()
        self._track.set_feedback(matches)
        winner = 2 if win else 1
        score = RoundScore(
            player1=0,
            player2=self._elapsed_ms,
            winner=winner,
        )
        self.flow.scores.append(score)
        QTimer.singleShot(1200, self.round_done.emit)

    def _on_live(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)

    def _on_feedback(self, matches: list, _n_ok: int) -> None:
        self._track.set_feedback(matches)

    def _on_round_won(self) -> None:
        self._track.set_feedback([True] * SLOTS)

    def _on_round_lost(self, reference: list) -> None:
        # P1 wins (P2 couldn't recreate).
        self._finished = True
        self._tick.stop()
        self._track.set_feedback([False] * SLOTS)
        score = RoundScore(player1=0, player2=self._elapsed_ms, winner=1)
        self.flow.scores.append(score)
        QTimer.singleShot(1200, self.round_done.emit)

    def _on_phase(self, _phase: Phase) -> None:
        pass

    def _on_status(self, msg: str) -> None:
        self._status.setText(msg)
