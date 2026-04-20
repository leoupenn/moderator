"""Figma 21:477 / 45:789 — Time Challenge gameplay (MP head-to-head + SP variant).

Uses GameSession for pad input / audio. Each round picks a target pattern from
a per-level library; the timer tracks how long the player takes to match it
(or, in SP, to recreate the phrase). Lower elapsed time = winner.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...game_logic import Phase, SLOTS
from ...session import FlowState, GameMode, GameSession
from ...session.flow_state import LevelTier, RoundScore
from ..theme import DESIGN_W, THEME
from ..widgets import (
    ChoiceButton,
    ChoiceStyle,
    DuckMascot,
    FlowPage,
    RhythmTrackGrid,
)
from ..widgets.asset_loader import svg_widget


_LEVEL_PATTERNS: dict[LevelTier, List[List[int]]] = {
    LevelTier.EASY: [
        [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
        [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    ],
    LevelTier.NORMAL: [
        [1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0],
        [1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1],
    ],
    LevelTier.EXPERT: [
        [1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1],
        [1, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
    ],
}


def _format_ms(ms: int) -> str:
    total_s = ms // 1000
    m = total_s // 60
    s = total_s % 60
    cs = (ms % 1000) // 10
    return f"{m:02d}:{s:02d}:{cs:02d}"


class _PlayerCard(QFrame):
    def __init__(self, name: str, accent_blue: bool) -> None:
        super().__init__()
        self.setObjectName("CardBlue" if accent_blue else "CardYellow")
        self.setFixedSize(450, 468)

        col = QVBoxLayout(self)
        col.setContentsMargins(48, 20, 48, 42)
        col.setSpacing(24)

        self.player_title = QLabel(name)
        self.player_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        self.player_title.setFont(pf)
        self.player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.player_title)

        col.addStretch(1)

        self.time_lbl = QLabel("00:00:00")
        self.time_lbl.setObjectName("TimeDigits")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(96)
        self.time_lbl.setFont(tf)
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.time_lbl)

        self.attempt_lbl = QLabel("Attempt 1")
        self.attempt_lbl.setObjectName("AttemptLabel")
        af = QFont(THEME.font_display)
        af.setPixelSize(52)
        self.attempt_lbl.setFont(af)
        self.attempt_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.attempt_lbl)

        col.addStretch(1)

        self.submit_hint = QLabel("Press D to submit")
        self.submit_hint.setObjectName("SubmitHint")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(36)
        self.submit_hint.setFont(sf)
        self.submit_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.submit_hint)

    def set_time_ms(self, ms: int) -> None:
        self.time_lbl.setText(_format_ms(ms))

    def set_attempt(self, n: int) -> None:
        self.attempt_lbl.setText(f"Attempt {n}")


class TimeChallengePage(FlowPage):
    round_complete = Signal()  # one round scored; MainWindow routes to results

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

        sub = QLabel("Time Challenge", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(40)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(35, 101)

        self._round_label = QLabel("ROUND 1", self)
        self._round_label.setObjectName("Kicker")
        rlf = QFont(THEME.font_display)
        rlf.setPixelSize(32)
        self._round_label.setFont(rlf)
        self._round_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 220, 88)

        strip = QFrame(self)
        strip.setObjectName("RhythmStrip")
        strip.setGeometry(213, 172, 1086, 130)
        strip_lbl = QLabel("Play the rhythm...", strip)
        strip_lbl.setObjectName("StripLabel")
        ssf = QFont(THEME.font_display)
        ssf.setPixelSize(40)
        strip_lbl.setFont(ssf)
        strip_lbl.adjustSize()
        strip_lbl.move(50, 45)
        self._strip_label = strip_lbl

        self._track = RhythmTrackGrid(self)
        self._track.move(213, 330)

        self._p1_card = _PlayerCard("Player 1", accent_blue=True)
        self.place(self._p1_card, 213, 540)

        self._p2_card = _PlayerCard("Player 2", accent_blue=False)
        self.place(self._p2_card, 849, 540)
        self._p2_card.submit_hint.setText("Press K to submit")

        p1_duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        p1_duck.move(154, 480)
        self._p1_duck = p1_duck

        p2_duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        p2_duck.move(1220, 480)
        self._p2_duck = p2_duck

        # Bottom controls: play reference + new round.
        play_btn = ChoiceButton("Play target", ChoiceStyle.DARK, width=220, height=64, parent=self)
        pf = QFont(THEME.font_display)
        pf.setPixelSize(28)
        play_btn.setFont(pf)
        play_btn.move(213, 880)
        play_btn.clicked.connect(session.play_reference)

        skip_btn = ChoiceButton("Skip / Next round", ChoiceStyle.BLUE, width=260, height=64, parent=self)
        skip_btn.setFont(pf)
        skip_btn.move(1039, 880)
        skip_btn.clicked.connect(self._force_finish_round)
        self._next_btn = skip_btn

        # Timer / state
        self._match_start: Optional[float] = None
        self._elapsed_ms_p1 = 0
        self._elapsed_ms_p2 = 0
        self._p1_done = False
        self._p2_done = False
        self._attempts_p1 = 1
        self._attempts_p2 = 1
        self._current_player = 1  # alternates or 1/2 depending on mode

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)

        session.live_pattern_changed.connect(self._on_live_pattern)
        session.feedback_ready.connect(self._on_feedback)
        session.round_won.connect(self._on_round_won)
        session.phase_changed.connect(self._on_phase)

    # ----- match lifecycle -------------------------------------------------
    def on_enter(self) -> None:
        self._p1_duck.set_asset(self.flow.character_p1.asset)
        self._p2_duck.set_asset(self.flow.character_p2.asset)
        if self.flow.mode == GameMode.SINGLE:
            self._p2_card.setVisible(False)
            self._p2_duck.setVisible(False)
        else:
            self._p2_card.setVisible(True)
            self._p2_duck.setVisible(True)
        self._session.set_bpm(self.flow.bpm)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._start_round()

    def _start_round(self) -> None:
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)

        target = self._pick_pattern()
        self._session.set_manual_pattern(target)
        self._track.clear()
        self._strip_label.setText("Play the rhythm...")

        self._elapsed_ms_p1 = 0
        self._elapsed_ms_p2 = 0
        self._p1_done = False
        self._p2_done = False
        self._attempts_p1 = 1
        self._attempts_p2 = 1
        self._current_player = 1
        self._match_start = time.monotonic()
        self._p1_card.set_time_ms(0)
        self._p2_card.set_time_ms(0)
        self._p1_card.set_attempt(1)
        self._p2_card.set_attempt(1)
        self._tick.start(50)

    def _pick_pattern(self) -> List[int]:
        choices = _LEVEL_PATTERNS.get(self.flow.level, _LEVEL_PATTERNS[LevelTier.NORMAL])
        idx = (self.flow.current_round - 1) % len(choices)
        return choices[idx]

    def _on_tick(self) -> None:
        if self._match_start is None:
            return
        elapsed = int((time.monotonic() - self._match_start) * 1000)
        if not self._p1_done:
            self._elapsed_ms_p1 = elapsed
            self._p1_card.set_time_ms(elapsed)
        if self.flow.mode == GameMode.MULTI and not self._p2_done:
            self._elapsed_ms_p2 = elapsed
            self._p2_card.set_time_ms(elapsed)

    # ----- keyboard handles ------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_D,):
            self._submit_for(1)
        elif key in (Qt.Key.Key_K,):
            if self.flow.mode == GameMode.MULTI:
                self._submit_for(2)
        elif key == Qt.Key.Key_Space:
            self._session.play_reference()
        else:
            super().keyPressEvent(event)

    # ----- submission / scoring --------------------------------------------
    def _submit_for(self, player: int) -> None:
        if player == 1 and self._p1_done:
            return
        if player == 2 and self._p2_done:
            return
        self._current_player = player
        res = self._session.p2_submit()
        if res is None:
            return
        matches, n_ok = res
        if n_ok == SLOTS:
            self._complete_player(player)
        else:
            if player == 1:
                self._attempts_p1 += 1
                self._p1_card.set_attempt(self._attempts_p1)
            else:
                self._attempts_p2 += 1
                self._p2_card.set_attempt(self._attempts_p2)
            self._track.set_feedback(matches)
            QTimer.singleShot(900, self._session.feedback_continue)
            QTimer.singleShot(950, self._track.clear)

    def _complete_player(self, player: int) -> None:
        if player == 1:
            self._p1_done = True
            self._strip_label.setText("Player 1 got it!")
        else:
            self._p2_done = True
            self._strip_label.setText("Player 2 got it!")
        done_condition = (
            self._p1_done
            if self.flow.mode == GameMode.SINGLE
            else self._p1_done and self._p2_done
        )
        if done_condition:
            self._tick.stop()
            self._record_round_result()
            QTimer.singleShot(800, self.round_complete.emit)

    def _record_round_result(self) -> None:
        if self.flow.mode == GameMode.SINGLE:
            score = RoundScore(player1=self._elapsed_ms_p1, player2=0, winner=1)
        else:
            winner = (
                1
                if self._elapsed_ms_p1 < self._elapsed_ms_p2
                else (2 if self._elapsed_ms_p2 < self._elapsed_ms_p1 else None)
            )
            score = RoundScore(
                player1=self._elapsed_ms_p1,
                player2=self._elapsed_ms_p2,
                winner=winner,
            )
        self.flow.scores.append(score)

    def _force_finish_round(self) -> None:
        if self._p1_done and (self.flow.mode == GameMode.SINGLE or self._p2_done):
            return
        self._tick.stop()
        # Penalize incomplete players with a large time so the round still scores.
        BIG = 10 * 60 * 1000  # 10 minutes
        if not self._p1_done:
            self._elapsed_ms_p1 = BIG
            self._p1_done = True
        if self.flow.mode == GameMode.MULTI and not self._p2_done:
            self._elapsed_ms_p2 = BIG
            self._p2_done = True
        self._record_round_result()
        self.round_complete.emit()

    # ----- session signal plumbing -----------------------------------------
    def _on_live_pattern(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)

    def _on_feedback(self, matches: list, _n_ok: int) -> None:
        self._track.set_feedback(matches)

    def _on_round_won(self) -> None:
        self._track.set_feedback([True] * SLOTS)

    def _on_phase(self, _phase: Phase) -> None:
        pass
