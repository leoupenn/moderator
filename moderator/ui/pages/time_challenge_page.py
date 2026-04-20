"""Figma 21:477 / 45:789 — Time Challenge gameplay (MP head-to-head + SP variant).

Uses GameSession for pad input / audio. Each round picks a target pattern from
a per-level library; the timer tracks how long the player takes to match it
(or, in SP, to recreate the phrase). Lower elapsed time = winner.

When FlowState.network_role is HOST / CLIENT, the page operates as a
networked match:

- Host owns the round timer, picks the target, and computes the authoritative
  winner. It runs P1 locally and waits for the client's ``submit`` / timeout
  for P2.
- Client renders the host's state. It runs P2 locally (reading its own
  controller) and pushes submits + live pattern updates back to the host.

The shared clock is a host-issued ``start_epoch_ms``. The host anchors
against its own ``time.time()``; the client translates the host's epoch into
its local clock frame using ``NetworkManager.host_to_local_ms`` (NTP-style
offset measured at connect time). If that offset hasn't been sampled yet,
the client falls back to anchoring on the arrival time of ``MSG_START_ROUND``
— this trades the old wall-clock drift for sub-second one-way network
latency so two machines with skewed OS clocks still show the same timer.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...game_logic import Phase, SLOTS, binary_pattern_for_playback, compare_patterns
from ...net import (
    MSG_INPUT_PATTERN,
    MSG_PLAY_REFERENCE,
    MSG_ROUND_RESULT,
    MSG_START_ROUND,
    MSG_SUBMIT,
)
from ...session import FlowState, GameMode, GameSession, NetworkRole
from ...session.flow_state import LevelTier, RoundScore
from ..theme import DESIGN_W, THEME
from ..widgets import (
    ChoiceButton,
    ChoiceStyle,
    DuckMascot,
    FlowPage,
    RhythmTrackGrid,
)


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


_BIG_PENALTY_MS = 10 * 60 * 1000  # 10-minute penalty for unfinished submits


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
        self.setFixedSize(450, 410)

        col = QVBoxLayout(self)
        col.setContentsMargins(36, 18, 36, 24)
        col.setSpacing(8)

        self.player_title = QLabel(name)
        self.player_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(44)
        self.player_title.setFont(pf)
        self.player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.player_title)

        col.addStretch(1)

        self.time_lbl = QLabel("00:00:00")
        self.time_lbl.setObjectName("TimeDigits")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(80)
        self.time_lbl.setFont(tf)
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.time_lbl)

        self.attempt_lbl = QLabel("Attempt 1")
        self.attempt_lbl.setObjectName("AttemptLabel")
        af = QFont(THEME.font_display)
        af.setPixelSize(40)
        self.attempt_lbl.setFont(af)
        self.attempt_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.attempt_lbl)

        col.addStretch(1)

        self.submit_hint = QLabel("Press D to submit")
        self.submit_hint.setObjectName("SubmitHint")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(28)
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

        self._track = RhythmTrackGrid(
            self, width=1086, height=96, cell_size=(96, 72), cell_radius=12
        )
        self._track.move(213, 310)

        self._p1_card = _PlayerCard("Player 1", accent_blue=True)
        self.place(self._p1_card, 213, 420)

        self._p2_card = _PlayerCard("Player 2", accent_blue=False)
        self.place(self._p2_card, 849, 420)
        self._p2_card.submit_hint.setText("Press K to submit")

        p1_duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        p1_duck.move(154, 372)
        self._p1_duck = p1_duck

        p2_duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        p2_duck.move(1220, 372)
        self._p2_duck = p2_duck

        # Bottom controls: play reference + force-end round.
        play_btn = ChoiceButton("Play target", ChoiceStyle.DARK, width=220, height=64, parent=self)
        pf = QFont(THEME.font_display)
        pf.setPixelSize(28)
        play_btn.setFont(pf)
        play_btn.move(213, 870)
        play_btn.clicked.connect(self._on_play_clicked)
        self._play_btn = play_btn

        skip_btn = ChoiceButton("Skip / Next round", ChoiceStyle.BLUE, width=320, height=64, parent=self)
        skip_btn.setFont(pf)
        skip_btn.move(979, 870)
        skip_btn.clicked.connect(self._force_finish_round)
        self._next_btn = skip_btn

        # Round state. Timings stored in ms. ``elapsed_ms_local_pN`` is what
        # each *machine* measured for that player; the host copy wins when
        # both are reported.
        self._start_epoch_ms: Optional[int] = None
        self._elapsed_ms_p1 = 0
        self._elapsed_ms_p2 = 0
        self._p1_done = False
        self._p2_done = False
        self._attempts_p1 = 1
        self._attempts_p2 = 1
        self._last_target: List[int] = [0] * SLOTS
        self._round_locked = False

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

        role = self.flow.network_role
        # Hide the host-only "Skip / Next round" button for the client; host is
        # the sole authority on ending a round.
        self._next_btn.setVisible(role != NetworkRole.CLIENT)
        self._play_btn.setVisible(role != NetworkRole.CLIENT)

        if role == NetworkRole.CLIENT:
            # Clients wait for the host to push ``start_round`` before their
            # timer kicks in. Initialise the visuals but don't pick a pattern
            # — that's the host's job.
            self._reset_round_visuals()
            self._strip_label.setText("Waiting for host…")
            return

        self._start_round_as_host()

    def _start_round_as_host(self) -> None:
        target = self._pick_pattern()
        self._last_target = list(target)
        self._session.set_manual_pattern(target)
        start_epoch_ms = int(time.time() * 1000)
        self._begin_round(target, start_epoch_ms)

        if self.flow.network_role == NetworkRole.HOST:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_START_ROUND,
                    round=self.flow.current_round,
                    start_epoch_ms=start_epoch_ms,
                    target=list(target),
                    bpm=self.flow.bpm,
                )

    def _begin_round(self, target: List[int], start_epoch_ms: int) -> None:
        self._round_locked = False
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)
        self._last_target = list(target)
        self._session.set_manual_pattern(list(target))
        self._reset_round_visuals()
        self._start_epoch_ms = start_epoch_ms
        self._tick.start(50)

    def _reset_round_visuals(self) -> None:
        self._track.clear()
        self._strip_label.setText("Play the rhythm...")
        self._elapsed_ms_p1 = 0
        self._elapsed_ms_p2 = 0
        self._p1_done = False
        self._p2_done = False
        self._attempts_p1 = 1
        self._attempts_p2 = 1
        self._p1_card.set_time_ms(0)
        self._p2_card.set_time_ms(0)
        self._p1_card.set_attempt(1)
        self._p2_card.set_attempt(1)

    def _pick_pattern(self) -> List[int]:
        choices = _LEVEL_PATTERNS.get(self.flow.level, _LEVEL_PATTERNS[LevelTier.NORMAL])
        idx = (self.flow.current_round - 1) % len(choices)
        return choices[idx]

    def _on_tick(self) -> None:
        if self._start_epoch_ms is None:
            return
        now_ms = int(time.time() * 1000)
        elapsed = max(0, now_ms - self._start_epoch_ms)
        if not self._p1_done:
            self._elapsed_ms_p1 = elapsed
            self._p1_card.set_time_ms(elapsed)
        if self.flow.mode == GameMode.MULTI and not self._p2_done:
            self._elapsed_ms_p2 = elapsed
            self._p2_card.set_time_ms(elapsed)

    # ----- keyboard handles ------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        role = self.flow.network_role
        if key == Qt.Key.Key_D:
            if role in (NetworkRole.SOLO, NetworkRole.HOST):
                self._submit_for(1)
            # client: ignore D, only P2 submits here
        elif key == Qt.Key.Key_K:
            if self.flow.mode != GameMode.MULTI:
                return super().keyPressEvent(event)
            if role == NetworkRole.CLIENT:
                self._submit_for(2)
            elif role == NetworkRole.SOLO:
                self._submit_for(2)
            # host+keyboard: keep local K submit working for solo testing
            elif role == NetworkRole.HOST:
                self._submit_for(2)
        elif key == Qt.Key.Key_Space:
            if role in (NetworkRole.SOLO, NetworkRole.HOST):
                self._on_play_clicked()
        else:
            super().keyPressEvent(event)

    # ----- submission / scoring --------------------------------------------
    def _submit_for(self, player: int) -> None:
        if self._round_locked:
            return
        if player == 1 and self._p1_done:
            return
        if player == 2 and self._p2_done:
            return
        role = self.flow.network_role

        if role == NetworkRole.CLIENT:
            # Client only submits P2 via the network; host is the sole judge.
            attempt = binary_pattern_for_playback(self._session.live_state)
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_SUBMIT,
                    player=2,
                    pattern=list(attempt),
                    client_elapsed_ms=int(self._elapsed_ms_p2),
                )
            return

        # Solo or host-local submit → route through GameSession so that LED
        # feedback, audio, and the phase state machine behave exactly as they
        # did pre-networking.
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

    def _score_submission(self, player: int, attempt: List[int]) -> None:
        """Host-side (or solo) scoring for an attempted pattern."""
        matches, n_ok = compare_patterns(self._last_target, attempt)
        if n_ok == SLOTS:
            self._complete_player(player)
            self._track.set_feedback(matches)
            return
        if player == 1:
            self._attempts_p1 += 1
            self._p1_card.set_attempt(self._attempts_p1)
        else:
            self._attempts_p2 += 1
            self._p2_card.set_attempt(self._attempts_p2)
        self._track.set_feedback(matches)
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
            self._lock_and_finish_round()

    def _lock_and_finish_round(self) -> None:
        if self._round_locked:
            return
        self._round_locked = True
        self._tick.stop()
        self._record_round_result()

        if self.flow.network_role == NetworkRole.HOST:
            mw = self._main_window()
            if mw is not None:
                winner = self.flow.scores[-1].winner if self.flow.scores else None
                mw.net.send(
                    MSG_ROUND_RESULT,
                    elapsed_p1=int(self._elapsed_ms_p1),
                    elapsed_p2=int(self._elapsed_ms_p2),
                    attempts_p1=int(self._attempts_p1),
                    attempts_p2=int(self._attempts_p2),
                    winner=winner,
                )
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
        if self._round_locked:
            return
        if self.flow.network_role == NetworkRole.CLIENT:
            # Clients don't force-end; host is authoritative.
            return
        if self._p1_done and (self.flow.mode == GameMode.SINGLE or self._p2_done):
            return
        if not self._p1_done:
            self._elapsed_ms_p1 = _BIG_PENALTY_MS
            self._p1_done = True
        if self.flow.mode == GameMode.MULTI and not self._p2_done:
            self._elapsed_ms_p2 = _BIG_PENALTY_MS
            self._p2_done = True
        self._lock_and_finish_round()

    # ----- reference audio -------------------------------------------------
    def _on_play_clicked(self) -> None:
        self._session.play_reference()
        if self.flow.network_role == NetworkRole.HOST:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(MSG_PLAY_REFERENCE)

    # ----- session signal plumbing -----------------------------------------
    def _on_live_pattern(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)
        # Clients forward their live pad state so the host can echo it (so P1's
        # screen can optionally visualise P2's attempt in future work).
        if self.flow.network_role == NetworkRole.CLIENT and not self._round_locked:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_INPUT_PATTERN, player=2, pattern=list(pattern[:SLOTS])
                )

    def _on_feedback(self, matches: list, _n_ok: int) -> None:
        self._track.set_feedback(matches)

    def _on_round_won(self) -> None:
        self._track.set_feedback([True] * SLOTS)

    def _on_phase(self, _phase: Phase) -> None:
        pass

    # ----- network message handling ---------------------------------------
    def handle_network_message(self, msg: dict) -> None:
        """Called by MainWindow for every inbound gameplay message."""
        kind = msg.get("type")
        role = self.flow.network_role

        if kind == MSG_START_ROUND and role == NetworkRole.CLIENT:
            target = msg.get("target") or []
            if len(target) < SLOTS:
                target = list(target) + [0] * (SLOTS - len(target))
            host_start_epoch_ms = int(
                msg.get("start_epoch_ms", time.time() * 1000)
            )
            # Translate the host's epoch into this machine's ``time.time()``
            # frame. If the NTP-style offset has landed, apply it so both
            # sides count the same elapsed. Otherwise anchor on arrival so
            # the client's display tracks its own clock (off by ~one-way
            # latency, not by the raw wall-clock skew between OS clocks).
            mw = self._main_window()
            if mw is not None and mw.net.is_clock_synced:
                local_start_ms = mw.net.host_to_local_ms(host_start_epoch_ms)
            else:
                local_start_ms = int(time.time() * 1000)
            rnd = msg.get("round")
            if isinstance(rnd, int):
                self.flow.current_round = rnd
            bpm = msg.get("bpm")
            if isinstance(bpm, int):
                self.flow.bpm = bpm
                self._session.set_bpm(bpm)
            self._begin_round(target[:SLOTS], local_start_ms)
            return

        if kind == MSG_PLAY_REFERENCE and role == NetworkRole.CLIENT:
            self._session.play_reference()
            return

        if kind == MSG_SUBMIT and role == NetworkRole.HOST:
            player = int(msg.get("player", 2))
            pattern = msg.get("pattern") or []
            if player == 2 and not self._p2_done and not self._round_locked:
                # Pin the authoritative elapsed time at the moment we process
                # the submit rather than trusting ``client_elapsed_ms``.
                self._elapsed_ms_p2 = self._current_elapsed_ms()
                self._p2_card.set_time_ms(self._elapsed_ms_p2)
                self._score_submission(2, list(pattern[:SLOTS]))
            return

        if kind == MSG_INPUT_PATTERN and role == NetworkRole.HOST:
            # Optional: show P2's live pattern somewhere on the host UI later.
            return

        if kind == MSG_ROUND_RESULT and role == NetworkRole.CLIENT:
            self._elapsed_ms_p1 = int(msg.get("elapsed_p1", 0))
            self._elapsed_ms_p2 = int(msg.get("elapsed_p2", 0))
            self._attempts_p1 = int(msg.get("attempts_p1", 1))
            self._attempts_p2 = int(msg.get("attempts_p2", 1))
            self._p1_card.set_time_ms(self._elapsed_ms_p1)
            self._p2_card.set_time_ms(self._elapsed_ms_p2)
            self._p1_card.set_attempt(self._attempts_p1)
            self._p2_card.set_attempt(self._attempts_p2)
            winner = msg.get("winner")
            score = RoundScore(
                player1=self._elapsed_ms_p1,
                player2=self._elapsed_ms_p2,
                winner=winner if winner in (1, 2) else None,
            )
            self.flow.scores.append(score)
            self._round_locked = True
            self._tick.stop()
            # The host will follow up with a nav to "results"; client simply
            # waits for it — no local round_complete emission needed.
            return

    # ----- helpers ---------------------------------------------------------
    def _current_elapsed_ms(self) -> int:
        if self._start_epoch_ms is None:
            return 0
        return max(0, int(time.time() * 1000) - self._start_epoch_ms)

    def _main_window(self):
        """Walk up the parent chain to the MainWindow that owns the NetworkManager."""
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
