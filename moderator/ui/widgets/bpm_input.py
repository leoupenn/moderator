"""BPM pill input used on Recreate Rhythm (Figma node 31:1186)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QWidget


class BpmInput(QFrame):
    """White rounded pill: 'Set BPM' label on the left, number field on the right."""

    value_changed = Signal(int)

    def __init__(self, initial: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BpmPill")
        self.setFixedSize(398, 96)

        row = QHBoxLayout(self)
        row.setContentsMargins(30, 12, 20, 12)
        row.setSpacing(12)

        label = QLabel("Set BPM")
        label.setObjectName("BpmLabel")
        row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

        row.addStretch(1)

        self._spin = QSpinBox()
        self._spin.setObjectName("BpmBox")
        self._spin.setRange(20, 300)
        self._spin.setFixedSize(134, 60)
        self._spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin.setValue(initial)
        self._spin.valueChanged.connect(self.value_changed.emit)
        row.addWidget(self._spin, 0, Qt.AlignmentFlag.AlignVCenter)

    def value(self) -> int:
        return self._spin.value()

    def set_value(self, bpm: int) -> None:
        self._spin.setValue(bpm)
