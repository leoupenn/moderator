"""16-slot rhythm matrix + playback bar."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..game_logic import SLOTS, feedback_led_chars, slot_role
from .theme import THEME


def _mono_font() -> QFont:
    f = QFont("Menlo", 10)
    if not f.exactMatch():
        f = QFont("Consolas", 10)
    if not f.exactMatch():
        f = QFont("monospace", 10)
    return f


class RhythmGridWidget(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        t = THEME
        outer = QVBoxLayout(self)
        outer.setContentsMargins(t.space * 2, t.space * 2, t.space * 2, t.space * 2)
        outer.setSpacing(t.space)

        title = QLabel("Rhythm — 16 steps (even = start, odd = end)")
        title.setObjectName("CardTitle")
        outer.addWidget(title)

        self._role_labels: list[QLabel] = []
        self._idx_labels: list[QLabel] = []
        self.cells: list[QLabel] = []

        role_row = QWidget()
        rlay = QHBoxLayout(role_row)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(4)
        mono = _mono_font()
        for i in range(SLOTS):
            r = QLabel("S" if slot_role(i) == "start" else "E")
            r.setAlignment(Qt.AlignmentFlag.AlignCenter)
            r.setFont(mono)
            r.setStyleSheet(f"color: {t.text_muted}; font-size: 10px;")
            self._role_labels.append(r)
            rlay.addWidget(r, 1)
        outer.addWidget(role_row)

        idx_row = QWidget()
        ilay = QHBoxLayout(idx_row)
        ilay.setContentsMargins(0, 0, 0, 0)
        ilay.setSpacing(4)
        for i in range(SLOTS):
            ix = QLabel(str(i))
            ix.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ix.setFont(mono)
            ix.setStyleSheet(f"color: {t.text_muted}; font-size: 9px;")
            self._idx_labels.append(ix)
            ilay.addWidget(ix, 1)
        outer.addWidget(idx_row)

        cell_row = QWidget()
        clay = QHBoxLayout(cell_row)
        clay.setContentsMargins(0, 0, 0, 0)
        clay.setSpacing(4)
        for i in range(SLOTS):
            lab = QLabel("0")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setMinimumSize(36, 40)
            lab.setFont(mono)
            self._apply_idle_cell(lab)
            self.cells.append(lab)
            clay.addWidget(lab, 1)
        outer.addWidget(cell_row)

        self.playback_label = QLabel("")
        self.playback_label.setFont(mono)
        self.playback_label.setStyleSheet(f"color: {t.text_secondary};")
        self.playback_label.setWordWrap(True)
        outer.addWidget(self.playback_label)

    def _apply_idle_cell(self, cell: QLabel) -> None:
        t = THEME
        cell.setStyleSheet(
            f"background-color: {t.cell_idle_bg}; color: {t.cell_idle_fg};"
            f"border-radius: {t.radius_sm}px; padding: 4px; border: 1px solid {t.border};"
        )

    def paint_live_slot(self, index: int, value: int) -> None:
        cell = self.cells[index]
        t = THEME
        active = bool(value)
        cell.setText("1" if active else "0")
        if active:
            cell.setStyleSheet(
                f"background-color: {t.cell_live_on_bg}; color: {t.cell_live_on_fg};"
                f"border-radius: {t.radius_sm}px; padding: 4px; font-weight: 600;"
                f"border: 1px solid {t.success_soft};"
            )
        else:
            self._apply_idle_cell(cell)

    def apply_feedback(self, matches: List[bool]) -> None:
        chars = feedback_led_chars(matches)
        t = THEME
        for i, ok in enumerate(matches):
            cell = self.cells[i]
            cell.setText(chars[i])
            if ok:
                cell.setStyleSheet(
                    f"background-color: {t.cell_ok_bg}; color: {t.cell_ok_fg};"
                    f"border-radius: {t.radius_sm}px; padding: 4px; font-weight: 600;"
                    f"border: 1px solid {t.success_soft};"
                )
            else:
                cell.setStyleSheet(
                    f"background-color: {t.cell_bad_bg}; color: {t.cell_bad_fg};"
                    f"border-radius: {t.radius_sm}px; padding: 4px; font-weight: 600;"
                    f"border: 1px solid {t.danger_soft};"
                )

    def reset_live(self, state: List[int]) -> None:
        for i, v in enumerate(state):
            self.paint_live_slot(i, int(v))

    def clear_playback(self) -> None:
        self.playback_label.setText("")
