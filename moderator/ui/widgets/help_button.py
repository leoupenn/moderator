"""Top-right Help component (settings + question chips) from Figma node 21:344."""
from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .asset_loader import asset_path


class HelpButton(QWidget):
    """Two 40×40 circular chips: settings and question mark."""

    settings_clicked = Signal()
    question_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        self.setFixedSize(94, 40)

        self._settings = self._make_chip("help_setting.svg")
        self._settings.clicked.connect(self.settings_clicked.emit)
        row.addWidget(self._settings)

        self._question = self._make_chip("help_question.svg")
        self._question.clicked.connect(self.question_clicked.emit)
        row.addWidget(self._question)

    @staticmethod
    def _make_chip(svg_name: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("HelpChip")
        btn.setFixedSize(40, 40)
        btn.setCursor(btn.cursor())
        btn.setIcon(QIcon(str(asset_path(svg_name))))
        btn.setIconSize(QSize(24, 24))
        btn.setFlat(True)
        return btn
