# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(root / 'doof' / '__main__.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'frontend' / 'dist'), 'frontend/dist'),
        (str(root / 'data'), 'data'),
        (str(root / 'assets'), 'assets'),
        (str(root / 'checkpoints'), 'checkpoints'),
    ],
    hiddenimports=[
        'doof', 'doof.api', 'doof.model', 'doof.inference',
        'doof.training', 'doof.tokenizer', 'doof.cloud',
        'doof.gui', 'doof.gui.app',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='DOOF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
