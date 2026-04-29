"""Base page class — provides design-canvas positioning and a persistent Help chip."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

from ...session.flow_state import NetworkRole
from ..theme import DESIGN_H, DESIGN_W, THEME
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
        # Pages rely on keyboard shortcuts (submit/play/skip). Ensure the page
        # can accept focus so keyPressEvent handlers run reliably.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoFillBackground(True)
        # Background is painted via the global QSS rule #PageBackground.
        self._role_marker = QLabel("", self)
        self._role_marker_plain = False
        self._role_marker.setFixedSize(160, 40)
        self._role_marker.move(1197, 32)
        self._role_marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rf = QFont(THEME.font_display)
        rf.setPixelSize(28)
        self._role_marker.setFont(rf)
        self._role_marker.hide()

        self._help = HelpButton(self)
        self._help.move(1377, 32)
        self._role_marker.raise_()
        self._help.raise_()

    @property
    def help_button(self) -> HelpButton:
        return self._help

    def _main_window(self) -> Optional[QWidget]:
        """Resolve the running ``MainWindow`` (owns ``.net`` / ``broadcast_state``).

        The page stack is hosted inside a ``QGraphicsScene`` proxy, which
        breaks the QWidget parent chain — ``parentWidget()`` and
        ``self.window()`` return the orphaned stack rather than the main
        window. The cross-cutting fix is to find the only running
        ``QMainWindow`` that exposes ``.net`` via the QApplication registry.
        """
        w = self.parentWidget()
        while w is not None and not hasattr(w, "net"):
            w = w.parentWidget()
        if w is not None:
            return w
        app = QApplication.instance()
        if app is None:
            return None
        for top in app.topLevelWidgets():
            if isinstance(top, QMainWindow) and hasattr(top, "net"):
                return top
        return None

    def place(self, widget: QWidget, x: int, y: int, *, raise_: bool = False) -> None:
        widget.setParent(self)
        widget.move(int(x), int(y))
        if raise_:
            widget.raise_()
        else:
            self._role_marker.raise_()
            self._help.raise_()

    def configure_role_marker(
        self,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        font_px: int,
        alignment: Qt.AlignmentFlag,
        plain: bool,
    ) -> None:
        self._role_marker_plain = plain
        self._role_marker.setFixedSize(width, height)
        self._role_marker.move(x, y)
        self._role_marker.setAlignment(alignment)
        font = QFont(THEME.font_display)
        font.setPixelSize(font_px)
        self._role_marker.setFont(font)
        self._update_role_marker()

    def showEvent(self, event) -> None:  # noqa: D401 - Qt override
        super().showEvent(event)
        self._update_role_marker()
        self._role_marker.raise_()
        self._help.raise_()

    def _update_role_marker(self) -> None:
        role = self.flow.network_role
        if role == NetworkRole.SOLO:
            self._role_marker.hide()
            return
        player = 2 if role == NetworkRole.CLIENT else 1
        self._role_marker.setText(f"PLAYER {player}")
        if self._role_marker_plain:
            fg = THEME.accent_yellow if player == 2 else THEME.accent_blue
            self._role_marker.setStyleSheet(
                "QLabel {"
                " background: transparent;"
                f" color: {fg};"
                " border: none;"
                "}"
            )
            self._role_marker.show()
            return

        bg = THEME.accent_yellow if player == 2 else THEME.accent_blue
        fg = THEME.slate if player == 2 else THEME.white
        self._role_marker.setStyleSheet(
            "QLabel {"
            f" background: {bg};"
            f" color: {fg};"
            " border-radius: 20px;"
            " padding: 0 18px;"
            "}"
        )
        self._role_marker.show()
