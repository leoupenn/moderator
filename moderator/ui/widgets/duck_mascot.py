"""Duck mascot — scales a Figma-exported SVG to an arbitrary design size."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget

from .asset_loader import asset_path


class DuckMascot(QSvgWidget):
    """Thin wrapper around QSvgWidget pointing at a duck SVG in moderator/ui/assets."""

    def __init__(
        self,
        asset_name: str = "duck_large.svg",
        width: int = 124,
        height: int = 137,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(str(asset_path(asset_name)), parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_asset(self, asset_name: str) -> None:
        self.load(str(asset_path(asset_name)))
