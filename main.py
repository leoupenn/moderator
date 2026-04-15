#!/usr/bin/env python3
"""Entry point for the Moderator desktop app."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from moderator.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Moderator")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
