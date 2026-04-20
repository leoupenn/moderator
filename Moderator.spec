# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

_ROOT = Path(__file__).resolve().parent
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
app = BUNDLE(
    exe,
    name='Moderator.app',
    icon=None,
    bundle_identifier=None,
)
