# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all

# NOTE: In some environments (notably GitHub Actions), PyInstaller executes spec files
# with `__file__` unset. We rely on the workflow running PyInstaller from the repo root.
_ROOT = Path.cwd()
datas = [
    (str(p), "moderator/ui/assets")
    for p in (_ROOT / "moderator" / "ui" / "assets").glob("*.svg")
]
datas += [
    (str(p), "moderator/ui/assets/fonts")
    for p in (_ROOT / "moderator" / "ui" / "assets" / "fonts").glob("*.ttf")
]
datas.append(
    (
        str(_ROOT / "moderator" / "ui" / "styles.qss"),
        "moderator/ui",
    )
)
binaries = []
hiddenimports = []
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Moderator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Build outputs:
# - macOS: bundle as a .app
# - Windows/Linux: onedir folder (zip and ship the folder)
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Moderator.app",
        icon=None,
        bundle_identifier=None,
    )
else:
    app = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Moderator",
    )
