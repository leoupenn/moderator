"""Figma 113:2822 (Player 1) / 115:3177 (Player 2) — Time Challenge gameplay.

Refresh of the original head-to-head layout:

* Header ("COMPETITIVE MODE" / "Time Challenge" / "ROUND N") unchanged.
* Rhythm strip (1086×130 white pill at y=172) with a play icon on the right —
  clicking the strip plays the **local** pad-built rhythm after a one-bar (four
  quarter-note) metronome count-in, same as the orange ``Play Your Rhythm`` pill.
* Two player cards (450×561), gray for P1 and yellow for P2, each stacking
  Player title · timer digits · attempt counter · submit hint.
* A single "Play Your Rhythm" orange pill sits inside the *local* player's
  card (P1 for host / solo, P2 for client) so each machine has its own
  play-reference control. Playback stays local — no network broadcast.
* The 8-cell RhythmTrackGrid and the standalone "Play target" / "Skip"
  buttons from the old layout are gone. Skip / force-finish is still
  reachable via the ``N`` keyboard shortcut for testing.

Networking behaviour is otherwise identical to the previous revision:

- Host owns the round timer, picks the target, and computes the authoritative
  winner. It runs P1 locally and waits for the client's ``submit`` / timeout
  for P2.
- Client renders the host's state. It runs P2 locally (reading its own
  controller) and pushes submits + live pattern updates back to the host.
- The shared clock is still a host-issued ``start_epoch_ms`` translated into
  the client's local frame via ``NetworkManager.host_to_local_ms``.
"""
from __future__ import annotations

import time
from typing import List, Optional

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QKeyEvent,
    QKeySequence,
    QShortcut,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...game_logic import Phase, SLOTS, binary_pattern_for_playback, compare_patterns
from ...phrase_audio import DEFAULT_COUNT_IN_QUARTERS
from ...net import (
    MSG_ATTEMPTS_UPDATE,
    MSG_INPUT_PATTERN,
    MSG_ROUND_RESULT,
    MSG_START_ROUND,
    MSG_SUBMIT,
    MSG_TIME_CHALLENGE_CONTROL,
)
from ...session import FlowState, GameMode, GameSession, NetworkRole
from ...session.flow_state import LevelTier, RoundScore
from ..theme import DESIGN_W, THEME
from ..widgets import (
    DuckMascot,
    FlowPage,
)


# Multiplayer round 1 only: one bar at eighth-note resolution (16 steps).
# Even=start, odd=end (``game_logic.slot_role``): quarter (0–3), quarter rest
# (4–7), eighth + rest, eighth + rest (8–15).
_MULTI_ROUND1_PRESET: List[int] = [
    1,
    0,
    0,
    1,  # quarter: start 0, end 3
    0,
    0,
    0,
    0,  # quarter rest
    1,
    1,
    0,
    0,  # eighth + eighth rest (sound 8–9)
    1,
    1,
    0,
    0,  # eighth + eighth rest (sound 12–13)
]

_LEVEL_PATTERNS: dict[LevelTier, List[List[int]]] = {
    LevelTier.EASY: [
        # Round 1 (solo default): one quarter note at the downbeat, then rests for the bar.
        # Slots are even=start / odd=end (see ``game_logic.slot_role``); one
        # sustained note from step 0 through 3 lights the first two 8-cell
        # beats (each cell is a slot pair) and keeps the rest blank.
        [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
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

# Colors specific to the Time Challenge refresh (Figma 113:2822 / 115:3177).
# Kept local instead of bolted onto THEME because P1's card turning gray is a
# Time Challenge choice, not a global palette change.
_PLAYER1_CARD_BG = "#BFC0BF"
_PLAYER2_CARD_BG = THEME.accent_yellow  # "#DFC22C"
_PLAY_RHYTHM_ORANGE = "#E48706"
_PLAY_RHYTHM_ORANGE_HOVER = "#F29823"
_PLAY_RHYTHM_ORANGE_PRESSED = "#C27405"


def _format_ms(ms: int) -> str:
    total_s = ms // 1000
    m = total_s // 60
    s = total_s % 60
    cs = (ms % 1000) // 10
    return f"{m:02d}:{s:02d}:{cs:02d}"


class _PlayButton(QPushButton):
    """Orange "Play Your Rhythm" pill that lives inside a player's card."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Play Your Rhythm", parent)
        self.setObjectName("PlayYourRhythmBtn")
        self.setFixedSize(316, 54)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        f = QFont(THEME.font_display)
        f.setPixelSize(32)
        self.setFont(f)
        # Local stylesheet — none of the global pill rules match the exact
        # orange/size from the new design, so we scope it to this button.
        # Horizontal padding is kept tight so the long label isn't clipped
        # on systems that substitute a wider font for Jersey 10.
        self.setStyleSheet(
            "QPushButton#PlayYourRhythmBtn {"
            f"  background: {_PLAY_RHYTHM_ORANGE};"
            "   color: white;"
            "   border: none;"
            "   border-radius: 27px;"
            "   padding: 0 18px;"
            "}"
            "QPushButton#PlayYourRhythmBtn:hover {"
            f"  background: {_PLAY_RHYTHM_ORANGE_HOVER};"
            "}"
            "QPushButton#PlayYourRhythmBtn:pressed {"
            f"  background: {_PLAY_RHYTHM_ORANGE_PRESSED};"
            "}"
        )


class _PlayDuotoneIcon(QWidget):
    """Small play icon for the rhythm strip (dark circle + white triangle).

    Matches Figma ``Play_duotone`` (21:602) without pulling in a dedicated
    SVG asset. Painted manually so it scales with whatever size we hand it.
    """

    def __init__(self, diameter: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(diameter, diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event: QPaintEvent) -> None:
        d = float(min(self.width(), self.height()))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Outer circle — a muted slate matching Figma's `#2A4157` token.
        p.setPen(QPen(Qt.PenStyle.NoPen))
        p.setBrush(QBrush(QColor("#2A4157")))
        p.drawEllipse(QPointF(d / 2, d / 2), d / 2, d / 2)

        # Right-pointing triangle centred on the circle, slightly biased
        # right to feel visually balanced.
        t_h = d * 0.40
        t_w = t_h * 0.88
        cx = d / 2 + d * 0.04
        cy = d / 2
        tri = QPolygonF(
            [
                QPointF(cx - t_w / 2, cy - t_h / 2),
                QPointF(cx + t_w / 2, cy),
                QPointF(cx - t_w / 2, cy + t_h / 2),
            ]
        )
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawPolygon(tri)
        p.end()


class _PlayerCard(QFrame):
    """A 450×561 stacked card (title / time / attempt / optional play / hint).

    ``variant`` is ``"p1"`` or ``"p2"`` and picks the background + default
    submit hint wording. ``show_play_button`` wires in the orange "Play Your
    Rhythm" pill on the machine that owns this card.
    """

    play_rhythm = Signal()

    def __init__(
        self,
        name: str,
        *,
        variant: str,
        show_play_button: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(450, 561)
        bg = _PLAYER1_CARD_BG if variant == "p1" else _PLAYER2_CARD_BG
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 20px; border: none; }}"
        )

        col = QVBoxLayout(self)
        # Figma inset: pt=20, pl=65, pr=57, pb=42. The pl/pr are symmetric on
        # content so we average them; the hint sits 471px from the top which
        # leaves ~48px to the bottom after its 48px height.
        col.setContentsMargins(65, 20, 57, 42)
        col.setSpacing(0)

        self.player_title = QLabel(name, self)
        self.player_title.setObjectName("PlayerTitle")
        ptf = QFont(THEME.font_display)
        ptf.setPixelSize(48)
        self.player_title.setFont(ptf)
        self.player_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.player_title)

        col.addSpacing(84)  # Figma gap between title and timer block

        self.time_lbl = QLabel("00:00:00", self)
        self.time_lbl.setObjectName("TimeDigitsBig")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(128)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6.4)
        self.time_lbl.setFont(tf)
        self.time_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.time_lbl)

        col.addSpacing(10)

        self.attempt_lbl = QLabel("Attempt 1", self)
        self.attempt_lbl.setObjectName("AttemptLabel")
        af = QFont(THEME.font_display)
        af.setPixelSize(64)
        self.attempt_lbl.setFont(af)
        self.attempt_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.attempt_lbl)

        col.addStretch(1)

        if show_play_button:
            self.play_btn: Optional[_PlayButton] = _PlayButton(self)
            self.play_btn.clicked.connect(self.play_rhythm.emit)
            btn_row = QFrame(self)
            btn_row.setStyleSheet("background: transparent;")
            brl = QVBoxLayout(btn_row)
            brl.setContentsMargins(0, 0, 0, 0)
            brl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            brl.addWidget(self.play_btn, 0, Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(btn_row)
            col.addSpacing(14)
        else:
            self.play_btn = None

        default_hint = "Press D to Submit" if variant == "p1" else "Press K to Submit"
        self.submit_hint = QLabel(default_hint, self)
        self.submit_hint.setObjectName("SubmitHint")
        sf = QFont(THEME.font_numeric)
        sf.setPixelSize(48)
        self.submit_hint.setFont(sf)
        self.submit_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        # Match the Figma `#33363F` slate for the submit hint.
        self.submit_hint.setStyleSheet(
            f"color: {THEME.slate}; background: transparent;"
        )
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

        # Keyboard shortcuts must work even when a child widget has focus.
        # Some platforms/widgets won't reliably forward keyPressEvent up to the
        # page, so we bind explicit shortcuts with WidgetWithChildren context.
        self._sc_submit_p1 = QShortcut(QKeySequence(Qt.Key.Key_D), self)
        self._sc_submit_p1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._sc_submit_p1.activated.connect(lambda: self._submit_for(1))

        self._sc_submit_p2 = QShortcut(QKeySequence(Qt.Key.Key_K), self)
        self._sc_submit_p2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._sc_submit_p2.activated.connect(lambda: self._submit_for(2))

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

        # ----- rhythm strip (clickable, plays local pad pattern) -----------
        self._strip = QFrame(self)
        self._strip.setObjectName("RhythmStrip")
        self._strip.setGeometry(213, 172, 1086, 130)
        self._strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._strip.mousePressEvent = self._on_strip_clicked  # type: ignore[assignment]

        self._strip_label = QLabel("Play the Rhythm...", self._strip)
        self._strip_label.setObjectName("StripLabel")
        ssf = QFont(THEME.font_display)
        ssf.setPixelSize(40)
        self._strip_label.setFont(ssf)
        self._strip_label.move(47, 45)
        self._strip_label.adjustSize()

        self._play_icon = _PlayDuotoneIcon(80, self._strip)
        # Absolute 1180,197 on the page -> relative (1180-213, 197-172) = (967, 25).
        self._play_icon.move(967, 25)

        # ----- player cards ----------------------------------------------
        role = flow.network_role
        local_is_p1 = role in (NetworkRole.SOLO, NetworkRole.HOST)
        self._p1_card = _PlayerCard(
            "Player 1", variant="p1", show_play_button=local_is_p1, parent=self
        )
        self.place(self._p1_card, 213, 361)
        if self._p1_card.play_btn is not None:
            self._p1_card.play_rhythm.connect(self._on_play_clicked)

        self._p2_card = _PlayerCard(
            "Player 2", variant="p2", show_play_button=(role == NetworkRole.CLIENT),
            parent=self,
        )
        self.place(self._p2_card, 849, 361)
        if self._p2_card.play_btn is not None:
            self._p2_card.play_rhythm.connect(self._on_play_clicked)

        p1_duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        p1_duck.move(154, 313)
        self._p1_duck = p1_duck

        p2_duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        p2_duck.move(1220, 313)
        self._p2_duck = p2_duck

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
        # Ensure keyboard shortcuts (D/K/Space/N) go to this page, not a child.
        self.setFocus(Qt.FocusReason.OtherFocusReason)

        role = self.flow.network_role

        if role == NetworkRole.CLIENT and self.flow.mode == GameMode.MULTI:
            # Clients wait for the host to push ``start_round`` before their
            # timer kicks in. Initialise the visuals but don't pick a pattern
            # — that's the host's job.
            self._reset_round_visuals()
            self._strip_label.setText("Waiting for host…")
            self._strip_label.adjustSize()
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
        self._strip_label.setText("Play the Rhythm...")
        self._strip_label.adjustSize()
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
        # Push the reset counters to the client too so "Attempt 1" appears on
        # P2's card even before the first miss.
        self._broadcast_attempts()

    def _bump_attempts(self, player: int) -> None:
        """Increment the counter for a player and mirror it to the peer."""
        if player == 1:
            self._attempts_p1 += 1
            self._p1_card.set_attempt(self._attempts_p1)
        else:
            self._attempts_p2 += 1
            self._p2_card.set_attempt(self._attempts_p2)
        self._broadcast_attempts()

    def _broadcast_attempts(self) -> None:
        if self.flow.network_role != NetworkRole.HOST:
            return
        mw = self._main_window()
        if mw is None:
            return
        mw.net.send(
            MSG_ATTEMPTS_UPDATE,
            attempts_p1=int(self._attempts_p1),
            attempts_p2=int(self._attempts_p2),
        )

    def _pick_pattern(self) -> List[int]:
        if self.flow.mode == GameMode.MULTI and self.flow.current_round == 1:
            return list(_MULTI_ROUND1_PRESET)
        choices = _LEVEL_PATTERNS.get(self.flow.level, _LEVEL_PATTERNS[LevelTier.NORMAL])
        if self.flow.mode == GameMode.SINGLE:
            return list(choices[0])
        idx = (self.flow.current_round - 1) % len(choices)
        return list(choices[idx])

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
            # Single-player should always submit locally even if this instance
            # previously joined a network match (network_role may still be CLIENT).
            if self.flow.mode == GameMode.SINGLE or role in (NetworkRole.SOLO, NetworkRole.HOST):
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
            self._on_play_clicked()
        elif key == Qt.Key.Key_N:
            # Debug / fallback skip (the visible button from the old layout
            # is gone in the new design). Host/solo forces the round to end;
            # a client nudges the host via MSG_TIME_CHALLENGE_CONTROL.
            self._on_skip_requested()
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

        if role == NetworkRole.CLIENT and self.flow.mode == GameMode.MULTI:
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
            # Still grade locally for hardware feedback: this client has the
            # round target (from MSG_START_ROUND → set_manual_pattern), so
            # ``GameSession.p2_submit`` can drive NeoPixel red/green feedback
            # on *this* controller immediately without affecting host scoring.
            res = self._session.p2_submit(require_stable=False)
            if res is None:
                return
            _matches, n_ok = res
            # Even though the host is authoritative for scoring, keep the client
            # UI responsive: bump attempts + show "got it" immediately.
            if n_ok == SLOTS:
                self._complete_player(2)
                return
            self._bump_attempts(2)
            QTimer.singleShot(900, self._session.feedback_continue)
            return

        # Solo or host-local submit → route through GameSession so that LED
        # feedback, audio, and the phase state machine behave exactly as they
        # did pre-networking. The 8-cell visual feedback grid is gone from
        # this layout, but the hardware still gets its red/green per-slot
        # frame via ``GameSession.p2_submit``.
        res = self._session.p2_submit(require_stable=False)
        if res is None:
            return
        _matches, n_ok = res
        if n_ok == SLOTS:
            self._complete_player(player)
        else:
            self._bump_attempts(player)
            QTimer.singleShot(900, self._session.feedback_continue)

    def _score_submission(self, player: int, attempt: List[int]) -> None:
        """Host-side authoritative scoring of a remote (client) attempt."""
        _matches, n_ok = compare_patterns(self._last_target, attempt)
        if n_ok == SLOTS:
            self._complete_player(player)
            return
        self._bump_attempts(player)

    def _complete_player(self, player: int) -> None:
        if player == 1:
            self._p1_done = True
            self._strip_label.setText("Player 1 got it!")
        else:
            self._p2_done = True
            self._strip_label.setText("Player 2 got it!")
        self._strip_label.adjustSize()
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
            score = RoundScore(
                player1=self._elapsed_ms_p1,
                player2=0,
                winner=1,
                attempts_p1=int(self._attempts_p1),
                attempts_p2=1,
            )
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
                attempts_p1=int(self._attempts_p1),
                attempts_p2=int(self._attempts_p2),
            )
        self.flow.scores.append(score)

    # ----- skip (keyboard only; the old on-screen button is gone) ---------
    def _on_skip_requested(self) -> None:
        if self.flow.network_role == NetworkRole.CLIENT:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(MSG_TIME_CHALLENGE_CONTROL, action="force_next_round")
            return
        self._force_finish_round()

    def _force_finish_round(self) -> None:
        if self._round_locked:
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

    # ----- reference audio (local playback per machine) --------------------
    def _on_strip_clicked(self, _e: QMouseEvent) -> None:
        self._on_play_clicked()

    def _on_play_clicked(self) -> None:
        # Each machine previews the **connected controller** pattern (live
        # pads), not the round target — host hears P1's build, client hears
        # P2's. No network broadcast.
        self._session.play_current(count_in_quarters=DEFAULT_COUNT_IN_QUARTERS)

    def host_apply_play_reference(self) -> None:
        """Legacy network hook — kept so older clients still trigger local audio.

        The new design drops the shared "Play target" button in favour of
        per-player controls, so this is only called if a peer running an
        older build sends ``MSG_TIME_CHALLENGE_CONTROL {action: play_reference}``.
        Match current behaviour: play this machine's live pad pattern.
        """
        self._session.play_current(count_in_quarters=DEFAULT_COUNT_IN_QUARTERS)

    def host_apply_force_finish(self) -> None:
        """Host-only: force-end invoked from the network (``N`` on P2's machine)."""
        self._force_finish_round()

    # ----- session signal plumbing -----------------------------------------
    def _on_live_pattern(self, pattern: list) -> None:
        # Clients forward their live pad state so the host can echo it (so P1's
        # screen can optionally visualise P2's attempt in future work).
        if self.flow.network_role == NetworkRole.CLIENT and not self._round_locked:
            mw = self._main_window()
            if mw is not None:
                mw.net.send(
                    MSG_INPUT_PATTERN, player=2, pattern=list(pattern[:SLOTS])
                )

    def _on_round_won(self) -> None:
        # The 8-cell grid flash is gone; the per-player strip banner in
        # _complete_player already announces which player got it.
        pass

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

        if kind == MSG_SUBMIT and role == NetworkRole.HOST:
            player = int(msg.get("player", 2))
            pattern = msg.get("pattern") or []
            if player == 2 and not self._p2_done and not self._round_locked:
                self._elapsed_ms_p2 = self._current_elapsed_ms()
                self._p2_card.set_time_ms(self._elapsed_ms_p2)
                self._score_submission(2, list(pattern[:SLOTS]))
            return

        if kind == MSG_INPUT_PATTERN and role == NetworkRole.HOST:
            # Optional: show P2's live pattern somewhere on the host UI later.
            return

        if kind == MSG_ATTEMPTS_UPDATE and role == NetworkRole.CLIENT:
            self._attempts_p1 = int(msg.get("attempts_p1", self._attempts_p1))
            self._attempts_p2 = int(msg.get("attempts_p2", self._attempts_p2))
            self._p1_card.set_attempt(self._attempts_p1)
            self._p2_card.set_attempt(self._attempts_p2)
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
                attempts_p1=int(self._attempts_p1),
                attempts_p2=int(self._attempts_p2),
            )
            self.flow.scores.append(score)
            self._round_locked = True
            self._tick.stop()
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
