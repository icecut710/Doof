"""DOOF v0.2 — friend-ready onedir EXE build (Windows).

Run from the project root:

    python packaging/build_exe.py
    # or double-click / run:
    packaging\build.bat

Pipeline (ALWAYS in this order):
  1. npm install + production frontend build  →  frontend/dist/index.html
  2. Verify assets (icon, dist, checkpoint)
  3. PyInstaller onedir via packaging/doof.spec
  4. Copy .env.example next to DOOF.exe + print checklist

This is the ONLY supported way to ship a usable EXE. Skipping step 1
causes "Failed to load UI" / "Frontend UI is missing" at runtime.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str] | str, cwd: Path | None = None, shell: bool = False) -> None:
    print(f"[build] $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd or ROOT), shell=shell)
    if r.returncode != 0:
        print(f"[build] FAILED (exit {r.returncode})")
        sys.exit(r.returncode)


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").is_file():
        print("[build] ERROR: frontend/package.json missing")
        sys.exit(1)

    print("\n========== 1/4  FRONTEND PRODUCTION BUILD ==========")
    print("[build] npm install…")
    run("npm install", cwd=frontend, shell=True)

    print("[build] npm run build…")
    r = subprocess.run("npm run build", cwd=str(frontend), shell=True)
    if r.returncode != 0:
        print("[build] full build failed — trying build:fast (vite only)…")
        run("npm run build:fast", cwd=frontend, shell=True)

    index = frontend / "dist" / "index.html"
    if not index.is_file():
        print(f"[build] ERROR: expected {index}")
        print("[build] UI will NOT load in the EXE without this file.")
        sys.exit(1)
    print(f"[build] OK frontend → {index}")

    naddaf = frontend / "dist" / "mrnaddaf.png"
    if not naddaf.is_file():
        src = frontend / "public" / "mrnaddaf.png"
        if src.is_file():
            shutil.copy2(src, naddaf)
            print("[build] copied mrnaddaf.png into dist")
        else:
            print("[build] WARNING: mrnaddaf.png missing from frontend dist")


def verify_assets() -> None:
    print("\n========== 2/4  VERIFY ASSETS ==========")
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
        print("[build] WARNING: checkpoints/doof_v01.pt missing — first run bootstraps weights")


def build_exe() -> Path:
    print("\n========== 3/4  PYINSTALLER ONEDIR ==========")
    spec = ROOT / "packaging" / "doof.spec"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec)])
    out = ROOT / "dist" / "DOOF" / "DOOF.exe"
    if not out.is_file():
        alt = ROOT / "dist" / "DOOF" / "DOOF"
        if alt.is_file():
            return alt
        print(f"[build] ERROR: expected {out}")
        sys.exit(1)
    return out


def post_copy(exe: Path) -> None:
    print("\n========== 4/4  SHIP HELPERS ==========")
    dest_dir = exe.parent
    env_src = ROOT / ".env.example"
    if env_src.is_file():
        shutil.copy2(env_src, dest_dir / ".env.example")
        print(f"[build] copied .env.example → {dest_dir / '.env.example'}")
    readme = dest_dir / "README_FIRST.txt"
    readme.write_text(
        """DOOF v0.2 — first-run checklist\n"""
        "================================\n\n"
        "1. Copy .env.example to .env (same folder as DOOF.exe) OR\n"
        "   put .env in %LOCALAPPDATA%\\DOOF\\\n\n"
        "2. Fill in:\n"
        "   SUPABASE_URL=https://YOUR_PROJECT.supabase.co\n"
        "   SUPABASE_ANON_KEY=your_anon_key\n\n"
        "3. Supabase Dashboard → Authentication → URL Configuration:\n"
        "   Site URL:        http://127.0.0.1:8766\n"
        "   Redirect URLs:   http://127.0.0.1:8766/**\n"
        "                    http://127.0.0.1:8766/\n"
        "                    http://localhost:3000/**\n"
        "                    http://127.0.0.1:3000/**\n\n"
        "4. Enable Google provider under Authentication → Providers\n"
        "   (Client ID / Secret from Google Cloud Console)\n\n"
        "5. Double-click DOOF.exe\n\n"
        "Google button appears only when SUPABASE_URL + SUPABASE_ANON_KEY are set.\n"
        "Email confirmation links must be opened on this same PC (DOOF is listening).\n",
        encoding="utf-8",
    )
    print(f"[build] wrote {readme}")


def main() -> int:
    print("DOOF v0.2 friend-ready build")
    print(f"ROOT = {ROOT}")
    if sys.platform != "win32":
        print("[build] WARNING: QtWebEngine onedir EXE is intended for Windows.")
        print("[build] Continuing anyway (useful for validating the frontend step).")

    build_frontend()
    verify_assets()
    exe = build_exe()
    post_copy(exe)

    print("\n========== BUILD COMPLETE ==========")
    print(f"  EXE:  {exe}")
    print(f"  DIR:  {exe.parent}")
    print("  Zip the entire dist/DOOF/ folder to share with friends.")
    print("  Put .env next to DOOF.exe before first launch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
