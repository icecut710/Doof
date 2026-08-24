# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for DOOF v0.3 — friend-ready Windows EXE.

CRITICAL: Do NOT exclude torch.distributed.
Excluding it and pre-stubbing the module caused:
  AttributeError: partially initialized module 'torch' has no attribute 'distributed'

Output:
  dist/DOOF/DOOF.exe
  dist/DOOF/_internal/...

Build (from repo root, on Windows):
  packaging\\build.bat
  or:  python packaging/build_exe.py
"""

from pathlib import Path

_spec = Path(SPECPATH).resolve()
_candidates = [
    _spec.parent if _spec.name.lower() == "packaging" else None,
    _spec,
    _spec.parent,
    _spec.parent.parent,
]
ROOT = None
for c in _candidates:
    if c is None:
        continue
    if (c / "doof" / "__main__.py").is_file():
        ROOT = c
        break
if ROOT is None:
    raise SystemExit(
        f"Could not locate doof/__main__.py from SPECPATH={_spec}. "
        "Run PyInstaller from the DOOF repo root."
    )

def _datas():
    items = []
    pairs = [
        (ROOT / "frontend" / "dist", "frontend/dist"),
        (ROOT / "assets", "assets"),
        (ROOT / "checkpoints", "checkpoints"),
        (ROOT / "database", "database"),
        (ROOT / "releases", "releases"),
    ]
    train = ROOT / "data" / "train.txt"
    if train.is_file():
        pairs.append((train, "data_seed"))

    env_example = ROOT / ".env.example"
    if env_example.is_file():
        pairs.append((env_example, "."))

    for src, dest in pairs:
        if src.exists():
            items.append((str(src), dest))
    return items


block_cipher = None

a = Analysis(
    [str(ROOT / "doof" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=_datas(),
    hiddenimports=[
        "doof",
        "doof.api",
        "doof.api_extra",
        "doof.api_mount",
        "doof.paths",
        "doof.gui",
        "doof.gui.app",
        "doof.gui.main_window",
        "doof.inference",
        "doof.inference.generate",
        "doof.training",
        "doof.tokenizer",
        "doof.model",
        "doof.cloud",
        "doof.cloud.client",
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
        "doof.compute",
        "doof.compute.jobs",
        "doof.compute.scheduler",
        "doof.compute.pool",
        "doof.runtime",
        "doof.errors",
        "doof.personality",
        "doof.updates",
        "doof.updates.client",
        "doof.admin",
        "dotenv",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtPrintSupport",
        "shiboken6",
        "torch",
        "torch.cuda",
        "torch.nn",
        "torch.nn.functional",
        "torch.distributed",
        "tqdm",
        "http.server",
        "json",
        "hashlib",
        "uuid",
        "threading",
        "socket",
        "zipfile",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "rthooks" / "pyi_rth_doof_torch.py")],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "notebook",
        "pytest",
        "triton",
        "torch.testing",
        "torch.utils.tensorboard",
        "sympy",
        "networkx",
        # Do NOT exclude torch.distributed — required for clean torch import.
        # nvidia/cudnn may still be large; collect what the installed torch needs.
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = ROOT / "assets" / "doof.ico"
if not _icon.is_file():
    _icon = ROOT / "assets" / "doof_icon.ico"
if not _icon.is_file():
    # Prefer MRNADDAF visual identity when ico missing
    for cand in (ROOT / "assets" / "mrnaddaf.png", ROOT / "frontend" / "public" / "mrnaddaf.png"):
        if cand.is_file():
            break

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DOOF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_icon) if _icon.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DOOF",
)
