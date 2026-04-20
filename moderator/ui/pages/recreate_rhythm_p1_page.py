"""Figma 21:901 — Recreate Rhythm P1 ('Make a Rhythm!', BPM pill, submit)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ...session import FlowState, GameSession
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

        card = QFrame(self)
        card.setObjectName("CardBlue")
        card.setGeometry(352, 266, 866, 520)

        col = QVBoxLayout(card)
        col.setContentsMargins(48, 28, 48, 48)
        col.setSpacing(22)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        p1_title = QLabel("Player 1", card)
        p1_title.setObjectName("PlayerTitle")
        pf = QFont(THEME.font_display)
        pf.setPixelSize(48)
        p1_title.setFont(pf)
        p1_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(p1_title)

        hero = QLabel("Make a Rhythm!", card)
        hero.setObjectName("TimeDigits")
        hf = QFont(THEME.font_display)
        hf.setPixelSize(96)
        hero.setFont(hf)
        hero.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(hero)

        self._bpm = BpmInput(flow.bpm, card)
        col.addWidget(self._bpm, 0, Qt.AlignmentFlag.AlignHCenter)
        self._bpm.value_changed.connect(self._on_bpm)

        hint = QLabel("Press D to submit", card)
        hint.setObjectName("SubmitHint")
        hf2 = QFont(THEME.font_display)
        hf2.setPixelSize(36)
        hint.setFont(hf2)
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(hint)

        self._track = RhythmTrackGrid(self)
        self._track.move(221, 800)
        self._track.setVisible(False)  # live preview shows in a smaller place

        self._duck = DuckMascot(flow.character_p1.asset, 124, 137, self)
        self._duck.move(293, 218)

        # Submit + Preview buttons
        submit_btn = ChoiceButton("Submit", ChoiceStyle.DARK, width=220, height=64, parent=self)
        tbf = QFont(THEME.font_display)
        tbf.setPixelSize(28)
        submit_btn.setFont(tbf)
        submit_btn.move((DESIGN_W - 220) // 2 + 150, 800)
        submit_btn.clicked.connect(self._submit)

        preview_btn = ChoiceButton("Preview", ChoiceStyle.BLUE, width=220, height=64, parent=self)
        preview_btn.setFont(tbf)
        preview_btn.move((DESIGN_W - 220) // 2 - 150, 800)
        preview_btn.clicked.connect(session.play_current)

        session.live_pattern_changed.connect(self._on_live)
        session.status_changed.connect(self._on_status)

        self._status = QLabel("", self)
        self._status.setObjectName("StatusLine")
        self._status.setGeometry(35, 920, DESIGN_W - 70, 30)

    def on_enter(self) -> None:
        self._duck.set_asset(self.flow.character_p1.asset)
        self._round_label.setText(f"ROUND {self.flow.current_round}")
        self._round_label.adjustSize()
        self._round_label.move(DESIGN_W - 20 - self._round_label.width(), 88)
        self._session.start_new_match()
        self._session.set_bpm(self.flow.bpm)
        self._bpm.set_value(self.flow.bpm)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_bpm(self, v: int) -> None:
        self.flow.bpm = int(v)
        self._session.set_bpm(self.flow.bpm)

    def _on_live(self, pattern: list) -> None:
        self._track.set_live_pattern(pattern)

    def _on_status(self, msg: str) -> None:
        self._status.setText(msg)

    def _submit(self) -> None:
        ok = self._session.p1_submit()
        if ok:
            self.submitted.emit()
        else:
            self._status.setText("Rhythm pad reading not stable yet — hold still and retry.")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_D:
            self._submit()
        elif event.key() == Qt.Key.Key_Space:
            self._session.play_current()
        else:
            super().keyPressEvent(event)
