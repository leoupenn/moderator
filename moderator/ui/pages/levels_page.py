"""Figma 21:507 / 45:875 — 'Time Challenge — Levels' (Easy / Normal / Expert)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...net import MSG_SELECT_LEVEL
from ...session import FlowState, GameMode, NetworkRole
from ...session.flow_state import LevelTier
from ..theme import THEME
from ..widgets import ChoiceButton, ChoiceStyle, FlowPage


_LEVELS = [
    (
        LevelTier.EASY,
        "EASY",
        [("Tempo", "60 BPM"), ("Included Notes", "♩ ♪"), ("Rests", "None")],
    ),
    (
        LevelTier.NORMAL,
        "Normal",
        [
            ("Tempo", "80 BPM"),
            ("Included Notes", "♩ ♪ ♬"),
            ("Rests", "Quarter"),
        ],
    ),
    (
        LevelTier.EXPERT,
        "Expert",
        [
            ("Tempo", "110 BPM"),
            ("Included Notes", "Full set"),
            ("Rests", "Multiple"),
            ("Metronome", "Off"),
        ],
    ),
]


class LevelsPage(FlowPage):
    selected = Signal(object)  # LevelTier

    def __init__(self, flow: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(flow, parent)

        kicker = QLabel("COMPETITIVE MODE", self)
        kicker.setObjectName("HeroTitle")
        kf = QFont(THEME.font_display)
        kf.setPixelSize(THEME.size_display_hero)
        kicker.setFont(kf)
        kicker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        kicker.adjustSize()
        kicker.move(63, 32)

        sub = QLabel("Time Challenge", self)
        sub.setObjectName("HeroSubtitle")
        sf = QFont(THEME.font_display)
        sf.setPixelSize(THEME.size_heading_1)
        sub.setFont(sf)
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub.adjustSize()
        sub.move(63, 164)

        cards_host = QWidget(self)
        cards_host.setGeometry(63, 336, 1386, 488)
        row = QHBoxLayout(cards_host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(72)

        self._buttons: list[tuple[LevelTier, ChoiceButton]] = []
        for tier, title, attrs in _LEVELS:
            card, btn = self._make_card(title, attrs, tier)
            row.addWidget(card)
            self._buttons.append((tier, btn))

    def _make_card(
        self, title: str, attrs: list[tuple[str, str]], tier: LevelTier
    ) -> tuple[QFrame, ChoiceButton]:
        card = QFrame()
        card.setObjectName("LevelCard")
        card.setFixedSize(411, 488)

        col = QVBoxLayout(card)
        col.setContentsMargins(32, 24, 32, 24)
        col.setSpacing(18)

        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("LevelTitle")
        tf = QFont(THEME.font_display)
        tf.setPixelSize(40)
        title_lbl.setFont(tf)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        col.addWidget(title_lbl)

        for k, v in attrs:
            row = QLabel(f"{k}   ·   {v}")
            row.setObjectName("LevelAttr")
            af = QFont(THEME.font_display)
            af.setPixelSize(26)
            row.setFont(af)
            col.addWidget(row)

        col.addStretch(1)

        btn = ChoiceButton("Select this level", ChoiceStyle.BLUE, width=320, height=72)
        bf = QFont(THEME.font_display)
        bf.setPixelSize(28)
        btn.setFont(bf)
        btn.clicked.connect(lambda: self._pick(tier))
        col.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        return card, btn

    def _pick(self, tier: LevelTier) -> None:
        if (
            self.flow.network_role == NetworkRole.CLIENT
            and self.flow.mode == GameMode.MULTI
        ):
            mw = self._main_window()
            if mw is not None:
                mw.net.send(MSG_SELECT_LEVEL, level=tier.name)
            return
        self.flow.level = tier
        tempo = {LevelTier.EASY: 60, LevelTier.NORMAL: 80, LevelTier.EXPERT: 110}[tier]
        self.flow.bpm = tempo
        self.selected.emit(tier)

    def _main_window(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        return w
