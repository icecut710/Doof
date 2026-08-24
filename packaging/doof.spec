# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DOOF v0.2 Alpha — Windows EXE."""

from pathlib import Path

ROOT = Path(SPECPATH).parent

block_cipher = None

a = Analysis(
    [str(ROOT / "doof" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "frontend" / "dist"), "frontend/dist"),
        (str(ROOT / "assets"), "assets"),
    ],
    hiddenimports=[
        "doof",
        "doof.api",
        "doof.gui",
        "doof.gui.app",
        "doof.gui.main_window",
        "doof.inference",
        "doof.training",
        "doof.tokenizer",
        "doof.model",
        "doof.cloud",
        "doof.intelligence",
        "doof.intelligence.store",
        "doof.intelligence.rag",
        "doof.intelligence.quality",
        "doof.intelligence.dataset",
        "doof.intelligence.evaluate",
        "doof.intelligence.scheduler",
        "database",
        "database.local",
        "database.supabase",
        "dotenv",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtWebEngineWidgets",
        "torch",
        "tqdm",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DOOF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "doof_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DOOF",
)
