#!/usr/bin/env python3
"""Entry point for the Moderator desktop app.

Usage:

    python3 main.py                  # solo / local
    python3 main.py --host           # start a host session on the default port
    python3 main.py --host --port 8769
    python3 main.py --join 192.168.1.42
    python3 main.py --join 192.168.1.42 --port 8769

When ``--host`` or ``--join`` is provided the app auto-starts networking on
launch; you can still change roles later from the Settings drawer.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QTimer
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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Beat It! — Moderator desktop app")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--host",
        action="store_true",
        help="Start as host (Player 1) and accept an incoming client.",
    )
    mode.add_argument(
        "--join",
        metavar="IP",
        default=None,
        help="Join a host at IP as Player 2.",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8769,
        help="TCP port to bind (host) or connect to (join).",
    )
    # Qt will look at argv too, so only parse our flags and leave the rest.
    known, _unknown = p.parse_known_args(argv[1:])
    return known


def main() -> int:
    args = _parse_args(sys.argv)
    app = QApplication(sys.argv)
    app.setApplicationName("Beat It")
    _load_fonts()
    w = MainWindow()
    w.show()

    # Kick off networking *after* the event loop is running so Qt signals from
    # the background threads deliver cleanly to the main thread.
    if args.host:
        QTimer.singleShot(0, lambda: w.start_host(args.port))
    elif args.join:
        QTimer.singleShot(0, lambda: w.join_host(args.join, args.port))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
