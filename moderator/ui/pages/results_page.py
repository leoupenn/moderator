"""Figma 21:1223 / 21:1358 / 21:1827 — Time Challenge Results (round-by-round)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...net import MSG_REQUEST_NAV
from ...session import FlowState, GameMode, MultiplayerMode, NetworkRole
from ...session.flow_state import RoundScore, rr_recreator_player
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

        # Stack label + count vertically so "Attempts" is never clipped by a
        # wide digit font in a narrow card (the old HBox squeezed the caption).
        att_lbl = QLabel("Attempts")
        al = QFont(THEME.font_display)
        al.setPixelSize(32)
        att_lbl.setFont(al)
        att_lbl.setStyleSheet(f"color: {THEME.white};")
        att_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        att_val = QLabel("—")
        av = QFont(THEME.font_display)
        av.setPixelSize(64)
        att_val.setFont(av)
        att_val.setStyleSheet(f"color: {THEME.white};")
        att_val.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        att_col = QVBoxLayout()
        att_col.setContentsMargins(0, 4, 0, 0)
        att_col.setSpacing(4)
        att_col.addWidget(att_lbl)
        att_col.addWidget(att_val)

        att_host = QWidget()
        att_host.setLayout(att_col)
        col.addWidget(att_host)

        # Stash getters
        card.setProperty("_time_lbl", time_lbl)
        card.setProperty("_att_host", att_host)
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
        p1_att_host = self._p1_card.property("_att_host")
        p1_att = self._p1_card.property("_att_lbl")
        p2_time = self._p2_card.property("_time_lbl")
        p2_att_host = self._p2_card.property("_att_host")
        p2_att = self._p2_card.property("_att_lbl")

        p1_time.setText(_fmt_ms(latest.player1))
        p2_time.setText(_fmt_ms(latest.player2))
        p1_att.setText(str(latest.attempts_p1))
        p2_att.setText(str(latest.attempts_p2))

        p1_time.setVisible(True)
        p1_att_host.setVisible(True)
        p2_time.setVisible(True)
        p2_att_host.setVisible(True)

        if self.flow.mode == GameMode.SINGLE:
            self._p2_card.setVisible(False)
            self._p2_duck.setVisible(False)
        elif self.flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
            self._p2_card.setVisible(True)
            self._p2_duck.setVisible(True)
            recreator = rr_recreator_player(self.flow.current_round)
            show_p1 = recreator == 1
            p1_time.setVisible(show_p1)
            p1_att_host.setVisible(show_p1)
            p2_time.setVisible(not show_p1)
            p2_att_host.setVisible(not show_p1)
        else:
            self._p2_card.setVisible(True)
            self._p2_duck.setVisible(True)

    def _on_continue(self) -> None:
        if self.flow.network_role == NetworkRole.CLIENT and self.flow.mode == GameMode.MULTI:
            mw = self._main_window()
            if mw is None:
                return
            last = self.flow.current_round >= self.flow.rounds_total
            if last:
                route = "leaderboard"
            elif self.flow.multiplayer_mode == MultiplayerMode.RECREATE_RHYTHM:
                route = "rr_p1"
            else:
                route = "time_challenge"
            mw.net.send(MSG_REQUEST_NAV, route=route)
            return
        if self.flow.current_round >= self.flow.rounds_total:
            self.finished.emit()
        else:
            self.flow.current_round += 1
            self.next_round.emit()

    def _main_window(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
