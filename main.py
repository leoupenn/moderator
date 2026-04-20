#!/usr/bin/env python3
"""Entry point for the Moderator desktop app."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from moderator.main_window import MainWindow


_FONT_DIR = Path(__file__).resolve().parent / "moderator" / "ui" / "assets" / "fonts"


def _load_fonts() -> None:
    if not _FONT_DIR.exists():
        return
    for ttf in _FONT_DIR.glob("*.ttf"):
        try:
            data = ttf.read_bytes()
        except OSError:
            continue
        QFontDatabase.addApplicationFontFromData(QByteArray(data))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Beat It")
    _load_fonts()
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
