"""DOOF v0.2 — deterministic friend-ready onedir EXE build (Windows).

Run from the project root:

    python packaging/build_exe.py
    # or:
    packaging\\build.bat

Pipeline (ALWAYS in this order):
  0. Record git commit + wipe ROOT/build and ROOT/dist (never source trees)
  1. npm install + production frontend build  →  frontend/dist/index.html
     (NO build:fast fallback — failed Vite aborts the entire build)
  2. Verify frontend assets (index, Naddaf, audio if present in public/)
  3. PyInstaller onedir via packaging/doof.spec (--noconfirm --clean)
  4. Verify frozen package + write BUILD_INFO.txt + .env.example

This is the ONLY supported way to ship a usable EXE.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Bundled ambient track (audio.ts prefers ./arabicrap.mp3; Supabase is fallback only)
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


def clean_old_output() -> None:
    """Remove previous PyInstaller / dist output only — never source trees."""
    print("\n========== 0/5  CLEAN OLD OUTPUT ==========")
    for name in ("build", "dist"):
        path = ROOT / name
        if path.exists():
            print(f"[build] Removing old output: {path}")
            shutil.rmtree(path, ignore_errors=False)
            print(f"[build] Removed {name}/")
        else:
            print(f"[build] No existing {name}/ — skip")
    # Stale Vite dist would also ship old UI if we skipped npm run build;
    # production build rewrites it, but wipe so verification is unambiguous.
    fe_dist = ROOT / "frontend" / "dist"
    if fe_dist.exists():
        print(f"[build] Removing stale frontend/dist → {fe_dist}")
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
            print("[build] Restoring frontend/src/App.tsx via scripts/restore_music_app.py …")
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
    print("[build] npm install…")
    run("npm install", cwd=frontend, shell=True)

    print("[build] npm run build… (strict — no build:fast fallback)")
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
    print(f"[build] OK frontend → {index}")

    # Naddaf: Vite copies public/ → dist/; copy if missing
    naddaf = frontend / "dist" / NADDAF_NAME
    if not naddaf.is_file():
        src = frontend / "public" / NADDAF_NAME
        if src.is_file():
            shutil.copy2(src, naddaf)
            print(f"[build] copied {NADDAF_NAME} into frontend/dist")
        else:
            # assets/ fallback used by some older trees
            alt = ROOT / "assets" / NADDAF_NAME
            if alt.is_file():
                shutil.copy2(alt, naddaf)
                print(f"[build] copied {NADDAF_NAME} from assets/ into frontend/dist")
            else:
                print(f"[build] WARNING: {NADDAF_NAME} missing from frontend dist")

    # Audio: audio.ts uses ./arabicrap.mp3 first — must be in dist for offline EXE
    audio_public = frontend / "public" / AUDIO_NAME
    audio_dist = frontend / "dist" / AUDIO_NAME
    if audio_public.is_file():
        if not audio_dist.is_file():
            shutil.copy2(audio_public, audio_dist)
            print(f"[build] copied {AUDIO_NAME} into frontend/dist")
        else:
            print(f"[build] OK bundled audio → {audio_dist.relative_to(ROOT)}")
    else:
        print(
            f"[build] NOTE: no frontend/public/{AUDIO_NAME} — "
            "runtime will use Supabase public fallback if audio.ts is wired"
        )


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

    # Source-side signals (informational — do not fail if UI not wired yet)
    app = ROOT / "frontend" / "src" / "App.tsx"
    audio_ts = ROOT / "frontend" / "src" / "audio.ts"
    if app.is_file():
        app_txt = app.read_text(encoding="utf-8", errors="replace")
        if "doofAudio" in app_txt or "from \"./audio\"" in app_txt:
            print("[build] App.tsx references ambient audio engine")
        else:
            print("[build] NOTE: App.tsx does not reference doofAudio (music not wired in UI)")
    if audio_ts.is_file():
        print("[build] OK frontend/src/audio.ts present")

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
        print("[build] WARNING: checkpoints/doof_v01.pt missing — first run bootstraps weights")


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
    out = ROOT / "dist" / "DOOF" / "DOOF.exe"
    if not out.is_file():
        alt = ROOT / "dist" / "DOOF" / "DOOF"
        if alt.is_file():
            return alt
        print(f"[build] ERROR: expected {out}")
        sys.exit(1)
    return out


def verify_package(exe: Path, commit: str) -> None:
    print("\n========== 5/5  VERIFY FINAL PACKAGE ==========")
    dest = exe.parent
    if not exe.is_file():
        print(f"[build] ERROR: EXE missing: {exe}")
        sys.exit(1)
    print(f"[build] OK EXE {exe} ({exe.stat().st_size} bytes)")

    # Frozen UI lives under _internal/frontend/dist (onedir COLLECT datas)
    candidates = [
        dest / "_internal" / "frontend" / "dist" / "index.html",
        dest / "frontend" / "dist" / "index.html",
    ]
    index = next((p for p in candidates if p.is_file()), None)
    if index is None:
        print("[build] ERROR: packaged frontend/dist/index.html not found under dist/DOOF/")
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

    # Icon / checkpoint often land under _internal
    internal = dest / "_internal"
    icon_hits = list(internal.rglob("doof*.ico")) if internal.is_dir() else []
    if icon_hits:
        print(f"[build] OK packaged icon ({icon_hits[0].relative_to(ROOT)})")
    else:
        print("[build] WARNING: no doof*.ico found under _internal")

    ckpt_hits = list(internal.rglob("doof_v01.pt")) if internal.is_dir() else []
    if ckpt_hits:
        print(f"[build] OK packaged checkpoint ({ckpt_hits[0].relative_to(ROOT)})")
    else:
        print("[build] WARNING: doof_v01.pt not found in package (optional bootstrap)")

    # Ship helpers
    env_src = ROOT / ".env.example"
    if env_src.is_file():
        shutil.copy2(env_src, dest / ".env.example")
        print(f"[build] OK .env.example → {dest / '.env.example'}")
    else:
        print("[build] WARNING: .env.example missing from repo root")

    readme = dest / "README_FIRST.txt"
    readme.write_text(
        "DOOF v0.2 — first-run checklist\n"
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
        "SHARING WITH FRIENDS\n"
        "Zip the ENTIRE dist\\DOOF folder (DOOF.exe AND the _internal folder).\n"
        "Sending only DOOF.exe causes 'python DLL not found'.\n"
        "Friend machines do not need Python or Node installed.\n\n"
        "Google button appears only when SUPABASE_URL + SUPABASE_ANON_KEY are set.\n"
        "Email confirmation links must be opened on this same PC (DOOF is listening).\n"
        "Standalone EXEs do not see each other unless they join the same API host\n"
        "or share the same Supabase project.\n",
        encoding="utf-8",
    )
    print(f"[build] wrote {readme}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    info = dest / "BUILD_INFO.txt"
    info.write_text(
        f"DOOF v0.2\n"
        f"Git commit: {commit}\n"
        f"Build time: {stamp}\n"
        f"EXE: {exe.name}\n",
        encoding="utf-8",
    )
    print(f"[build] wrote {info}")


def main() -> int:
    commit = git_short_hash()
    print("DOOF v0.2 deterministic friend-ready build")
    print(f"ROOT = {ROOT}")
    print(f"Git commit: {commit}")
    if sys.platform != "win32":
        print("[build] WARNING: QtWebEngine onedir EXE is intended for Windows.")
        print("[build] Continuing anyway (useful for validating the frontend step).")

    clean_old_output()
    build_frontend()
    verify_frontend()
    verify_repo_assets()
    exe = build_exe()
    verify_package(exe, commit)

    print("")
    print("========================================")
    print(" DOOF BUILD COMPLETE")
    print(f" Commit: {commit}")
    print(f" EXE:    {exe}")
    print("========================================")
    print("  Zip the entire dist/DOOF/ folder to share with friends.")
    print("  Put .env next to DOOF.exe before first launch.")
    print(f"  Confirm BUILD_INFO.txt lists commit {commit}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
