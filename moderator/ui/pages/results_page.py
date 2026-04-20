"""Figma 21:1223 / 21:1358 / 21:1827 — Time Challenge Results (round-by-round)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...session import FlowState, GameMode
from ...session.flow_state import RoundScore
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, DuckMascot, FlowPage


def _fmt_ms(ms: int) -> str:
    total_s = ms // 1000
    m = total_s // 60
    s = total_s % 60
    cs = (ms % 1000) // 10
    return f"{m:02d}:{s:02d}:{cs:02d}"


class ResultsPage(FlowPage):
    next_round = Signal()
    finished = Signal()  # to leaderboard

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        kicker = QLabel("COMPETITIVE MODE", self)
        kf = QFont(THEME.font_display)
        kf.setPixelSize(64)
        kicker.setFont(kf)
        kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        kicker.adjustSize()
        kicker.move(35, 32)

        sub = QLabel("Round Results", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(40)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(35, 101)

        self._p1_card = self._make_card("Player 1", "CardBlue")
        self.place(self._p1_card, 220, 292)

        self._p2_card = self._make_card("Player 2", "CardYellow")
        self.place(self._p2_card, 836, 292)

        self._p1_duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        self._p1_duck.move(161, 244)
        self._p2_duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        self._p2_duck.move(1227, 244)

        self._continue = ChoiceButton("Continue", ChoiceStyle.DARK, parent=self)
        self._continue.move((DESIGN_W - 334) // 2, 820)
        self._continue.clicked.connect(self._on_continue)

    def _make_card(self, title: str, qss_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(qss_name)
        card.setFixedSize(450, 452)

        col = QVBoxLayout(card)
        col.setContentsMargins(48, 20, 48, 42)
        col.setSpacing(16)

        lbl = QLabel(title)
        lbl.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        lbl.setFont(pf)
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(lbl)

        col.addStretch(1)

        time_lbl = QLabel("00:00:00")
        time_lbl.setObjectName("TimeDigits")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(96)
        time_lbl.setFont(tf)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(time_lbl)

        att_row = QHBoxLayout()
        att_row.setContentsMargins(0, 0, 0, 0)

        att_lbl = QLabel("Attempts:")
        al = QFont(THEME.font_display)
        al.setPixelSize(48)
        att_lbl.setFont(al)
        att_lbl.setStyleSheet(f"color: {THEME.white};")
        att_row.addWidget(att_lbl)

        att_val = QLabel("—")
        av = QFont(THEME.font_display)
        av.setPixelSize(72)
        att_val.setFont(av)
        att_val.setStyleSheet(f"color: {THEME.white};")
        att_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        att_row.addWidget(att_val, 1, Qt.AlignmentFlag.AlignRight)

        att_host = QWidget()
        att_host.setLayout(att_row)
        col.addWidget(att_host)

        # Stash getters
        card.setProperty("_time_lbl", time_lbl)
        card.setProperty("_att_lbl", att_val)
        return card

    def on_enter(self) -> None:
        self._p1_duck.set_asset(self.flow.character_p1.asset)
        self._p2_duck.set_asset(self.flow.character_p2.asset)
        self._render_latest()
        last = self.flow.current_round >= self.flow.rounds_total
        self._continue.setText("See Leaderboard" if last else "Next Round")

    def _render_latest(self) -> None:
        if not self.flow.scores:
            return
        latest: RoundScore = self.flow.scores[-1]
        p1_time = self._p1_card.property("_time_lbl")
        p1_att = self._p1_card.property("_att_lbl")
        p2_time = self._p2_card.property("_time_lbl")
        p2_att = self._p2_card.property("_att_lbl")

        p1_time.setText(_fmt_ms(latest.player1))
        p2_time.setText(_fmt_ms(latest.player2))
        p1_att.setText(self._attempts_summary(latest, 1))
        p2_att.setText(self._attempts_summary(latest, 2))

        if self.flow.mode == GameMode.SINGLE:
            self._p2_card.setVisible(False)
            self._p2_duck.setVisible(False)
        else:
            self._p2_card.setVisible(True)
            self._p2_duck.setVisible(True)

    def _attempts_summary(self, s: RoundScore, player: int) -> str:
        # We don't store attempt count in RoundScore yet; compute a label from winner.
        if s.winner is None:
            return "Tie"
        return "WIN" if s.winner == player else "—"

    def _on_continue(self) -> None:
        if self.flow.current_round >= self.flow.rounds_total:
            self.finished.emit()
        else:
            self.flow.current_round += 1
            self.next_round.emit()
