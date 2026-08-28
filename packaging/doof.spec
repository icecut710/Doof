# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for DOOF v3.0 — friend-ready Windows EXE.

CRITICAL RULES:
  - Do NOT exclude torch.distributed (causes circular init)
  - Do NOT exclude sympy or networkx (torch needs them)
  - Use collect_all('torch') to get ALL DLLs including shm.dll deps
  - Test torch import from frozen environment before release

Build from repo root: python packaging/release.py
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

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

# Collect ALL torch files (DLLs, data, binaries) — prevents WinError 126
torch_datas, torch_binaries, torch_hiddenimports = collect_all("torch")

# Also collect sympy (torch dependency)
sympy_datas, sympy_binaries, sympy_hiddenimports = collect_all("sympy")

# Also collect networkx (torch dependency)
nx_datas, nx_binaries, nx_hiddenimports = collect_all("networkx")


def _datas():
    items = []
    pairs = [
        (ROOT / "frontend" / "dist", "frontend/dist"),
        (ROOT / "assets", "assets"),
        (ROOT / "checkpoints", "checkpoints"),
        (ROOT / "database", "database"),

        (ROOT / "packaging" / "updater", "packaging/updater"),
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
    binaries=torch_binaries + sympy_binaries + nx_binaries,
    datas=_datas() + torch_datas + sympy_datas + nx_datas,
    hiddenimports=[
        "doof",
        "doof.api",
        "doof.api_full",
        "doof.api_extra",
        "doof.api_mount",
        "doof.paths",
        "doof.gui",
        "doof.gui.app",
        "doof.inference",
        "doof.inference.generate",
        "doof.inference.router",
        "doof.training",
        "doof.tokenizer",
        "doof.tokenizer.byte_tokenizer",
        "doof.model",
        "doof.model.transformer",
        "doof.cloud",
        "doof.cloud.client",
        "doof.cloud.hosted_brain",
        "doof.models",
        "doof.models.manager",
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
        "doof.compute.pool_patch",
        "doof.compute.cloud_inference",
        "doof.networking",
        "doof.networking.tailscale",
        "doof.runtime",
        "doof.errors",
        "doof.personality",
        "doof.brain",
        "doof.rewards",
        "doof.training.trainer",
        "doof.training.worker",
        "doof.updates",
        "doof.updates.client",
        "doof.updates.apply_helper",
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
        # Torch and its dependencies
        "torch",
        "torch.cuda",
        "torch.nn",
        "torch.nn.functional",
        "torch.distributed",
        "torch.testing",
        "torch._C",
        "torch._C._fft",
        "torch._C._linalg",
        "torch._C._nested",
        "torch._C._nn",
        "torch._C._return_types",
        "torch._C._special",
        "torch._hub",
        "torch._jit_internal",
        "torch._lowrank",
        "torch._VF",
        "torch.cpu",
        "torch.utils",
        "torch.utils.data",
        "torch.utils._pytree",
        "torch.autograd",
        "torch.autograd.function",
        "torch.nn.parallel",
        "tqdm",
        "http.server",
        "json",
        "hashlib",
        "uuid",
        "threading",
        "socket",
        "zipfile",
    ] + torch_hiddenimports + sympy_hiddenimports + nx_hiddenimports,
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
        "torch.utils.tensorboard",
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Doof v3.0",
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
    name="Doof v3.0",
)
