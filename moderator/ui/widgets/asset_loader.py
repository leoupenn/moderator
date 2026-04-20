"""Helpers for loading SVGs exported from Figma into Qt."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QWidget

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def asset_path(name: str) -> Path:
    return _ASSET_DIR / name


def svg_widget(name: str, w: int, h: int, parent: Optional[QWidget] = None) -> QSvgWidget:
    widget = QSvgWidget(str(asset_path(name)), parent)
    widget.setFixedSize(w, h)
    widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return widget


@lru_cache(maxsize=32)
def duck_pixmap(name: str, width: int, height: int) -> QPixmap:
    path = asset_path(name)
    if not path.exists():
        pix = QPixmap(width, height)
        pix.fill(Qt.GlobalColor.transparent)
        return pix
    from PySide6.QtSvg import QSvgRenderer  # local import; not always needed

    renderer = QSvgRenderer(str(path))
    pix = QPixmap(QSize(width, height))
    pix.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter

    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return pix
