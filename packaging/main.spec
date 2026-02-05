# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files

SPEC_DIR = globals().get("SPECPATH", os.getcwd())
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, os.pardir))

hiddenimports = collect_submodules("pygame") + collect_submodules("pygame_gui")

binaries = collect_dynamic_libs("pygame")

# Include pygame/pygame_gui data files (themes, fonts, etc.)
datas = collect_data_files("pygame") + collect_data_files("pygame_gui") + [
    (os.path.join(PROJECT_ROOT, "assets", "*"), "assets"),
    (os.path.join(PROJECT_ROOT, "tools", "ffmpeg", "*"), "tools/ffmpeg"),
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, "src", "main.py")],
    pathex=[PROJECT_ROOT],
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
    name='main',
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
