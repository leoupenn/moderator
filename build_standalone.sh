#!/usr/bin/env bash
# Builds a single executable for the current OS (macOS, Windows, or Linux).
# Output: dist/Moderator (or Moderator.exe on Windows)
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements-build.txt
exec python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --name Moderator \
  --windowed \
  --onefile \
  --collect-all PySide6 \
  main.py
