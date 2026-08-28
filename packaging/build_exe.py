"""DOOF v3.0 — deterministic friend-ready onedir EXE build (Windows).

Run from the project root:

    python packaging/build_exe.py
    # or:
    packaging\\build.bat

Pipeline (ALWAYS in this order):
  0. Record git commit + wipe ROOT/build and ROOT/dist (never source trees)
  1. npm install + production frontend build  ->  frontend/dist/index.html
     (NO build:fast fallback -- failed Vite aborts the entire build)
  2. Verify frontend assets (index, Naddaf, audio if present in public/)
  3. PyInstaller onedir via packaging/doof.spec (--noconfirm --clean)
  4. Verify frozen package + write BUILD_INFO.txt + .env.example

CUDA PRESERVATION RULES:
  - NEVER uninstall or replace an existing CUDA torch installation.
  - Detect torch.cuda.is_available() before build and carry it through.
  - If CUDA is present, bundle CUDA DLLs and label the build GPU-enabled.
  - If CUDA is absent, build CPU-only and label accordingly.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

AUDIO_NAME = "arabicrap.mp3"
NADDAF_NAME = "mrnaddaf.png"


def run(cmd: list[str] | str, cwd: Path | None = None, shell: bool = False) -> None:
    print(f"[build] $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd or ROOT), shell=shell)
    if r.returncode != 0:
        print(f"[build] FAILED (exit {r.returncode})")
        sys.exit(r.returncode)


def git_short_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    return "unknown"


def detect_cuda() -> dict:
    """Detect CUDA torch and GPU capabilities. Never modifies the install."""
    info = {
        "cuda_available": False,
        "torch_version": None,
        "cuda_version": None,
        "gpu_name": None,
        "gpu_vram_gb": None,
        "build_label": "CPU-only",
    }
    try:
        import torch
        info["torch_version"] = torch.__version__
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["cuda_version"] = getattr(torch.version, "cuda", None)
            try:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                info["gpu_vram_gb"] = round(props.total_memory / (1024**3), 2)
            except Exception:
                pass
            info["build_label"] = "GPU (CUDA)"
    except ImportError:
        pass
    return info


def clean_old_output() -> None:
    """Remove previous PyInstaller / dist output only -- never source trees."""
    print("\n========== 0/5  CLEAN OLD OUTPUT ==========")
    for name in ("build", "dist"):
        path = ROOT / name
        if path.exists():
            print(f"[build] Removing old output: {path}")
            shutil.rmtree(path, ignore_errors=False)
            print(f"[build] Removed {name}/")
        else:
            print(f"[build] No existing {name}/ -- skip")
    fe_dist = ROOT / "frontend" / "dist"
    if fe_dist.exists():
        print(f"[build] Removing stale frontend/dist")
        shutil.rmtree(fe_dist, ignore_errors=False)
        print("[build] Removed frontend/dist/")


def _ensure_app_tsx() -> None:
    """If App.tsx was corrupted/placeholder, restore via scripts/restore_music_app.py."""
    app = ROOT / "frontend" / "src" / "App.tsx"
    restore = ROOT / "scripts" / "restore_music_app.py"
    if not app.is_file():
        print("[build] ERROR: frontend/src/App.tsx missing")
        sys.exit(1)
    text = app.read_text(encoding="utf-8", errors="replace").strip()
    if text == "PLACEHOLDER" or len(text) < 500:
        if restore.is_file():
            print("[build] Restoring frontend/src/App.tsx via scripts/restore_music_app.py ...")
            r = subprocess.run([sys.executable, str(restore)], cwd=str(ROOT))
            if r.returncode != 0:
                print("[build] ERROR: could not restore App.tsx")
                sys.exit(1)
        else:
            print("[build] ERROR: App.tsx is invalid and restore script is missing")
            sys.exit(1)


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").is_file():
        print("[build] ERROR: frontend/package.json missing")
        sys.exit(1)

    _ensure_app_tsx()

    print("\n========== 1/5  FRONTEND PRODUCTION BUILD ==========")
    print("[build] npm install...")
    run("npm install", cwd=frontend, shell=True)

    print("[build] npm run build... (strict -- no build:fast fallback)")
    r = subprocess.run("npm run build", cwd=str(frontend), shell=True)
    if r.returncode != 0:
        print("[build] ERROR: production Vite build failed.")
        print("[build] Refusing to package an EXE from a failed frontend build.")
        print("[build] Fix TypeScript/JSX errors, then re-run packaging\\build.bat")
        sys.exit(r.returncode or 1)

    index = frontend / "dist" / "index.html"
    if not index.is_file():
        print(f"[build] ERROR: expected {index}")
        print("[build] UI will NOT load in the EXE without this file.")
        sys.exit(1)
    print(f"[build] OK frontend -> {index}")

    naddaf = frontend / "dist" / NADDAF_NAME
    if not naddaf.is_file():
        src = frontend / "public" / NADDAF_NAME
        if src.is_file():
            shutil.copy2(src, naddaf)
            print(f"[build] copied {NADDAF_NAME} into frontend/dist")
        else:
            alt = ROOT / "assets" / NADDAF_NAME
            if alt.is_file():
                shutil.copy2(alt, naddaf)
                print(f"[build] copied {NADDAF_NAME} from assets/ into frontend/dist")
            else:
                print(f"[build] WARNING: {NADDAF_NAME} missing from frontend dist")

    audio_public = frontend / "public" / AUDIO_NAME
    audio_dist = frontend / "dist" / AUDIO_NAME
    if audio_public.is_file():
        if not audio_dist.is_file():
            shutil.copy2(audio_public, audio_dist)
            print(f"[build] copied {AUDIO_NAME} into frontend/dist")
        else:
            print(f"[build] OK bundled audio -> {audio_dist.relative_to(ROOT)}")
    else:
        print(f"[build] NOTE: no frontend/public/{AUDIO_NAME} -- skipped")


def verify_frontend() -> None:
    print("\n========== 2/5  VERIFY FRONTEND DIST ==========")
    fe = ROOT / "frontend" / "dist"
    required = [fe / "index.html"]
    for p in required:
        if not p.is_file():
            print(f"[build] ERROR: required frontend asset missing: {p}")
            sys.exit(1)
        print(f"[build] OK {p.relative_to(ROOT)}")

    naddaf = fe / NADDAF_NAME
    if naddaf.is_file():
        print(f"[build] OK {naddaf.relative_to(ROOT)} ({naddaf.stat().st_size} bytes)")
    else:
        print(f"[build] WARNING: {NADDAF_NAME} not in frontend/dist")

    audio = fe / AUDIO_NAME
    if audio.is_file():
        print(f"[build] OK {audio.relative_to(ROOT)} ({audio.stat().st_size} bytes)")
    elif (ROOT / "frontend" / "public" / AUDIO_NAME).is_file():
        print(f"[build] ERROR: {AUDIO_NAME} in public/ but missing from frontend/dist")
        sys.exit(1)

    print("FRONTEND PRODUCTION BUILD VERIFIED")


def verify_repo_assets() -> None:
    print("\n========== 3/5  VERIFY REPO ASSETS ==========")
    required = [
        ROOT / "frontend" / "dist" / "index.html",
        ROOT / "doof" / "__main__.py",
        ROOT / "packaging" / "doof.spec",
    ]
    for p in required:
        if not p.exists():
            print(f"[build] ERROR: required asset missing: {p}")
            sys.exit(1)
        print(f"[build] OK {p.relative_to(ROOT)}")

    icon = ROOT / "assets" / "doof_icon.ico"
    if not icon.is_file():
        icon = ROOT / "assets" / "doof.ico"
    if icon.is_file():
        print(f"[build] OK {icon.relative_to(ROOT)}")
    else:
        print("[build] WARNING: no app icon found in assets/")

    ckpt = ROOT / "checkpoints" / "doof_v01.pt"
    if ckpt.is_file():
        print(f"[build] OK {ckpt.relative_to(ROOT)}")
    else:
        print("[build] WARNING: checkpoints/doof_v01.pt missing -- first run bootstraps weights")


def build_exe() -> Path:
    print("\n========== 4/5  PYINSTALLER ONEDIR ==========")
    spec = ROOT / "packaging" / "doof.spec"
    if not spec.is_file():
        print(f"[build] ERROR: missing spec {spec}")
        sys.exit(1)
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(spec),
        ]
    )
    out = ROOT / "dist" / "Doof v3.0" / "Doof v3.0.exe"
    if not out.is_file():
        alt = ROOT / "dist" / "DOOF" / "DOOF.exe"
        if alt.is_file():
            return alt
        alt2 = ROOT / "dist" / "DOOF" / "DOOF"
        if alt2.is_file():
            return alt2
        print(f"[build] ERROR: expected {out}")
        sys.exit(1)
    return out


def verify_package(exe: Path, commit: str, cuda_info: dict) -> None:
    print("\n========== 5/5  VERIFY FINAL PACKAGE ==========")
    dest = exe.parent
    if not exe.is_file():
        print(f"[build] ERROR: EXE missing: {exe}")
        sys.exit(1)
    print(f"[build] OK EXE {exe} ({exe.stat().st_size} bytes)")

    # Verify NO real .env file is packaged (secrets leak)
    for candidate in [dest / ".env", dest / "_internal" / ".env"]:
        if candidate.is_file():
            print(f"[build] WARNING: real .env found at {candidate} -- removing for security")
            candidate.unlink()

    # Frozen UI lives under _internal/frontend/dist (onedir COLLECT datas)
    candidates = [
        dest / "_internal" / "frontend" / "dist" / "index.html",
        dest / "frontend" / "dist" / "index.html",
    ]
    index = next((p for p in candidates if p.is_file()), None)
    if index is None:
        print("[build] ERROR: packaged frontend/dist/index.html not found under dist/Doof v3.0/")
        for p in candidates:
            print(f"[build]   looked: {p}")
        sys.exit(1)
    print(f"[build] OK packaged UI {index.relative_to(ROOT)}")
    pkg_dist = index.parent

    naddaf = pkg_dist / NADDAF_NAME
    if naddaf.is_file():
        print(f"[build] OK packaged {NADDAF_NAME} ({naddaf.stat().st_size} bytes)")
    else:
        print(f"[build] WARNING: packaged {NADDAF_NAME} missing")

    audio = pkg_dist / AUDIO_NAME
    if (ROOT / "frontend" / "public" / AUDIO_NAME).is_file():
        if audio.is_file():
            print(f"[build] OK packaged {AUDIO_NAME} ({audio.stat().st_size} bytes)")
        else:
            print(f"[build] ERROR: {AUDIO_NAME} was in public/ but not in packaged frontend/dist")
            sys.exit(1)

    # Verify CUDA DLLs if CUDA build
    internal = dest / "_internal"
    if cuda_info["cuda_available"]:
        torch_lib = internal / "torch" / "lib"
        if torch_lib.is_dir():
            cuda_dlls = list(torch_lib.glob("*cuda*"))
            cublas_dlls = list(torch_lib.glob("*cublas*"))
            cudnn_dlls = list(torch_lib.glob("*cudnn*"))
            nvrtc_dlls = list(torch_lib.glob("*nvrtc*"))
            total = len(cuda_dlls) + len(cublas_dlls) + len(cudnn_dlls) + len(nvrtc_dlls)
            if total > 0:
                print(f"[build] OK CUDA DLLs in torch/lib/: {total} files (cuda/cublas/cudnn/nvrtc)")
            else:
                print("[build] WARNING: CUDA build but no CUDA DLLs found in torch/lib/")
        else:
            print("[build] WARNING: torch/lib/ not found -- cannot verify CUDA DLLs")

    # Checkpoint
    ckpt_hits = list(internal.rglob("doof_v01.pt")) if internal.is_dir() else []
    if ckpt_hits:
        print(f"[build] OK packaged checkpoint ({ckpt_hits[0].relative_to(ROOT)})")
    else:
        print("[build] WARNING: doof_v01.pt not found in package (optional bootstrap)")

    # Ship .env.example only -- never .env
    env_src = ROOT / ".env.example"
    if env_src.is_file():
        shutil.copy2(env_src, dest / ".env.example")
        print(f"[build] OK .env.example -> {dest / '.env.example'}")
    else:
        print("[build] WARNING: .env.example missing from repo root")

    # Build label
    build_label = cuda_info["build_label"]
    gpu_detail = ""
    if cuda_info["cuda_available"]:
        gpu_detail = f" | GPU: {cuda_info['gpu_name'] or '?'} ({cuda_info['gpu_vram_gb'] or '?'} GB)"

    readme = dest / "README_FIRST.txt"
    readme.write_text(
        f"DOOF v3.0 -- first-run checklist\n"
        f"================================\n\n"
        f"Build type: {build_label}{gpu_detail}\n\n"
        f"1. Copy .env.example to .env (same folder as Doof v3.0.exe) OR\n"
        f"   put .env in %LOCALAPPDATA%\\DOOF\\\n\n"
        f"2. Fill in:\n"
        f"   SUPABASE_URL=https://YOUR_PROJECT.supabase.co\n"
        f"   SUPABASE_ANON_KEY=your_anon_key\n\n"
        f"3. Double-click Doof v3.0.exe\n\n"
        f"SHARING WITH FRIENDS\n"
        f"Zip the ENTIRE dist\\Doof v3.0 folder (Doof v3.0.exe AND the _internal folder).\n"
        f"Sending only Doof v3.0.exe causes 'python DLL not found'.\n"
        f"Friend machines do not need Python or Node installed.\n\n"
        f"Google button appears only when SUPABASE_URL + SUPABASE_ANON_KEY are set.\n"
        f"Email confirmation links must be opened on this same PC (DOOF is listening).\n",
        encoding="utf-8",
    )
    print(f"[build] wrote {readme}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    info = dest / "BUILD_INFO.txt"
    info.write_text(
        f"DOOF v3.0\n"
        f"Build type:    {build_label}\n"
        f"Git commit:    {commit}\n"
        f"Build time:    {stamp}\n"
        f"EXE:           {exe.name}\n"
        f"Python:        {sys.version}\n"
        f"Platform:      {sys.platform}\n"
        f"Architecture:  {' '.join(__import__('platform').architecture())}\n"
        f"Torch version: {cuda_info['torch_version'] or 'not installed'}\n"
        f"CUDA version:  {cuda_info['cuda_version'] or 'N/A'}\n"
        f"GPU:           {cuda_info['gpu_name'] or 'N/A'}\n"
        f"GPU VRAM:      {cuda_info['gpu_vram_gb'] or 'N/A'} GB\n",
        encoding="utf-8",
    )
    print(f"[build] wrote {info}")


def main() -> int:
    commit = git_short_hash()
    cuda_info = detect_cuda()
    print("DOOF v3.0 deterministic friend-ready build")
    print(f"ROOT = {ROOT}")
    print(f"Git commit: {commit}")
    print(f"Build type: {cuda_info['build_label']}")
    if cuda_info["cuda_available"]:
        print(f"CUDA: {cuda_info['cuda_version']} | GPU: {cuda_info['gpu_name']} ({cuda_info['gpu_vram_gb']} GB)")
    else:
        print("CUDA: not available -- building CPU-only package")
    if sys.platform != "win32":
        print("[build] WARNING: QtWebEngine onedir EXE is intended for Windows.")
        print("[build] Continuing anyway (useful for validating the frontend step).")

    clean_old_output()
    build_frontend()
    verify_frontend()
    verify_repo_assets()
    exe = build_exe()
    verify_package(exe, commit, cuda_info)

    print("")
    print("========================================")
    print(" DOOF BUILD COMPLETE")
    print(f" Commit:  {commit}")
    print(f" Type:    {cuda_info['build_label']}")
    print(f" EXE:     {exe}")
    print("========================================")
    print("  Zip the entire dist/Doof v3.0/ folder to share with friends.")
    print("  Put .env next to Doof v3.0.exe before first launch.")
    print(f"  Confirm BUILD_INFO.txt lists commit {commit}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
