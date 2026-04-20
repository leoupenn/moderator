"""Base page class — provides design-canvas positioning and a persistent Help chip."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ..theme import DESIGN_H, DESIGN_W
from .help_button import HelpButton

if TYPE_CHECKING:
    from ...session import FlowState


class FlowPage(QWidget):
    """A page whose children are positioned in Figma's 1512×982 design coords.

    Subclasses implement `build(flow)` and call `place(widget, x, y)` for each
    absolutely-positioned child. The Help chip is added automatically in the
    top-right corner (1377, 32) to mirror every Figma frame.
    """

    def __init__(self, flow: "FlowState", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.flow = flow
        self.setObjectName("PageBackground")
        self.setFixedSize(DESIGN_W, DESIGN_H)
        self.setAutoFillBackground(True)
        # Background is painted via the global QSS rule #PageBackground.
        self._help = HelpButton(self)
        self._help.move(1377, 32)
        self._help.raise_()

    @property
    def help_button(self) -> HelpButton:
        return self._help

    def place(self, widget: QWidget, x: int, y: int, *, raise_: bool = False) -> None:
        widget.setParent(self)
        widget.move(int(x), int(y))
        if raise_:
            widget.raise_()
        else:
            self._help.raise_()

    def showEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().showEvent(event)
        self._help.raise_()
