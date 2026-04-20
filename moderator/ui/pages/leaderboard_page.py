"""Figma 21:1456 / 21:1859 — Final Leaderboard (total wins + overall winner modal)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...session import FlowState, GameMode
from ..theme import DESIGN_W, THEME
from ..widgets import ChoiceButton, ChoiceStyle, DuckMascot, FlowPage


class LeaderboardPage(FlowPage):
    back_home = Signal()

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        kicker = QLabel("COMPETITIVE MODE", self)
        kf = QFont(THEME.font_display)
        kf.setPixelSize(64)
        kicker.setFont(kf)
        kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        kicker.adjustSize()
        kicker.move(35, 32)

        sub = QLabel("Final Leaderboard", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(40)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(35, 101)

        self._p1_card, self._p1_val = self._make_card("Player 1 Total Wins", "CardBlue")
        self.place(self._p1_card, 220, 292)
        self._p2_card, self._p2_val = self._make_card("Player 2 Total Wins", "CardYellow")
        self.place(self._p2_card, 836, 292)

        self._p1_duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        self._p1_duck.move(161, 244)
        self._p2_duck = DuckMascot(flow.character_p2.asset, 124, 137, self)
        self._p2_duck.move(1227, 244)

        back = ChoiceButton("Back to Home", ChoiceStyle.DARK, width=426, height=91, parent=self)
        back.move((DESIGN_W - 426) // 2, 820)
        back.clicked.connect(self.back_home.emit)

        # Total result overlay (Figma node 21:1496).
        self._scrim = QFrame(self)
        self._scrim.setObjectName("Scrim")
        self._scrim.setGeometry(0, 0, DESIGN_W, self.height())

        modal = QFrame(self._scrim)
        modal.setObjectName("TotalResultCard")
        modal.setFixedSize(730, 330)
        modal.move((DESIGN_W - 730) // 2, (self.height() - 330) // 2)

        col = QVBoxLayout(modal)
        col.setContentsMargins(100, 60, 100, 60)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel("Total Result", modal)
        t.setObjectName("TotalResultTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(56)
        t.setFont(tf)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(t)

        self._winner = QLabel("", modal)
        self._winner.setObjectName("TotalResultWinner")
        wf = QFont(THEME.font_display)
        wf.setPixelSize(88)
        self._winner.setFont(wf)
        self._winner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._winner.setWordWrap(True)
        col.addWidget(self._winner)

        self._dismiss = ChoiceButton(
            "See scoreboard", ChoiceStyle.BLUE, width=300, height=64, parent=modal
        )
        df = QFont(THEME.font_display)
        df.setPixelSize(26)
        self._dismiss.setFont(df)
        self._dismiss.clicked.connect(self._scrim.hide)
        col.addWidget(self._dismiss, 0, Qt.AlignmentFlag.AlignCenter)

    def _make_card(self, title: str, style: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName(style)
        card.setFixedSize(450, 316)

        col = QVBoxLayout(card)
        col.setContentsMargins(48, 20, 48, 42)

        t = QLabel(title)
        t.setObjectName("PlayerTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(40)
        t.setFont(tf)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        col.addWidget(t)

        col.addStretch(1)

        v = QLabel("0")
        v.setObjectName("TimeDigits")
        vf = QFont(THEME.font_display)
        vf.setPixelSize(128)
        v.setFont(vf)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(v)
        return card, v

    def on_enter(self) -> None:
        self._p1_duck.set_asset(self.flow.character_p1.asset)
        self._p2_duck.set_asset(self.flow.character_p2.asset)
        self._p1_val.setText(str(self.flow.wins_p1()))
        self._p2_val.setText(str(self.flow.wins_p2()))

        if self.flow.mode == GameMode.SINGLE:
            self._p2_card.setVisible(False)
            self._p2_duck.setVisible(False)
            self._winner.setText("Match complete!")
        else:
            w1 = self.flow.wins_p1()
            w2 = self.flow.wins_p2()
            if w1 == w2:
                self._winner.setText("It's a Tie!")
            elif w1 > w2:
                self._winner.setText("Player 1 Wins!")
            else:
                self._winner.setText("Player 2 Wins!")
        self._scrim.show()
        self._scrim.raise_()
