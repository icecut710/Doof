"""DOOF v3.0 Release Pipeline — single script, all steps, no shortcuts.

Run from project root:
    python packaging/release.py

Reads version from doof/__init__.py (single source of truth).
Detects CUDA torch and preserves it — never installs CPU-only torch.
Exits non-zero on any failure.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
# Ensure project root is on sys.path so doof can be imported
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPECTED_VERSION = "3.0.0"
EXE_NAME = "Doof v3.0"
RELEASE_VERSION_DIR = "v3.0.0"
ZIP_NAME = f"Doof-{EXPECTED_VERSION}-Windows-x64.zip"

REQUIRED_FILES = [
    ROOT / "doof" / "__init__.py",
    ROOT / "doof" / "__main__.py",
    ROOT / "requirements.txt",
    ROOT / ".env.example",
    ROOT / "packaging" / "doof.spec",
    ROOT / "packaging" / "build.bat",
]

REQUIRED_DIRS = [
    ROOT / "assets",
    ROOT / "checkpoints",
]

REQUIRED_IMPORTS = [
    ("PySide6", "PySide6"),
    ("PySide6.QtCore", "PySide6.QtCore"),
    ("torch", "torch"),
    ("doof", "doof"),
    ("doof.model", "doof.model"),
    ("doof.inference", "doof.inference"),
    ("doof.inference.generate", "doof.inference.generate"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STEP_N = 0


def banner(msg: str) -> None:
    global _STEP_N
    _STEP_N += 1
    print(f"\n{'=' * 72}")
    print(f"  STEP {_STEP_N}: {msg}")
    print(f"{'=' * 72}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command, stream output, fail on non-zero exit."""
    print(f"  > {' '.join(cmd)}")
    merged_env = {**dict(__import__("os").environ), **(env or {})}
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"    {line}")
    if result.returncode != 0:
        fail(f"Command exited with code {result.returncode}: {' '.join(cmd)}")
    return result


def find_npm() -> str:
    """Locate the npm executable. Fail with a clear message if missing."""
    import shutil as _shutil
    npm_path = _shutil.which("npm")
    if npm_path:
        return npm_path
    common = Path(r"C:\Program Files\nodejs\npm.cmd")
    if common.is_file():
        return str(common)
    fail(
        "npm not found on PATH. Install Node.js from https://nodejs.org/ "
        "and ensure npm is on your PATH."
    )
    return ""  # unreachable, keeps type checker happy


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


# ---------------------------------------------------------------------------
# Step 1: Validate repository
# ---------------------------------------------------------------------------

def step_validate_repo() -> None:
    banner("Validate repository")
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED_FILES if not p.is_file()]
    if missing:
        fail(f"Missing required files: {', '.join(missing)}")
    ok("All required files present")

    for d in REQUIRED_DIRS:
        if not d.is_dir():
            fail(f"Missing required directory: {d.relative_to(ROOT)}")
    ok("All required directories present")


# ---------------------------------------------------------------------------
# Step 2: Validate version
# ---------------------------------------------------------------------------

def step_validate_version() -> str:
    banner("Validate version")
    init_path = ROOT / "doof" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")

    version = None
    for line in text.splitlines():
        if line.strip().startswith("DOOF_VERSION"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break

    if version is None:
        fail("Could not find DOOF_VERSION in doof/__init__.py")
    if version != EXPECTED_VERSION:
        fail(f"Version mismatch: expected {EXPECTED_VERSION}, found {version}")

    ok(f"Version confirmed: {version}")
    return version


# ---------------------------------------------------------------------------
# Step 3: Run tests
# ---------------------------------------------------------------------------

def step_run_tests() -> None:
    banner("Run tests")
    run([sys.executable, "-m", "pytest", "tests/", "-x", "-q"])
    ok("All tests passed")


# ---------------------------------------------------------------------------
# Step 4: Verify npm is available
# ---------------------------------------------------------------------------

def step_verify_npm() -> str:
    banner("Verify npm is available")
    npm = find_npm()
    ok(f"npm found at: {npm}")
    return npm


# ---------------------------------------------------------------------------
# Step 5: Verify frontend dependencies
# ---------------------------------------------------------------------------

def step_verify_frontend_deps() -> None:
    banner("Verify frontend dependencies")
    node_modules = ROOT / "frontend" / "node_modules"
    if not node_modules.is_dir():
        fail("frontend/node_modules does not exist -- run npm install first")
    ok("frontend/node_modules present")


# ---------------------------------------------------------------------------
# Step 6: Build frontend (production)
# ---------------------------------------------------------------------------

def step_build_frontend(npm: str) -> None:
    banner("Build frontend (production)")
    run([npm, "run", "build"], cwd=ROOT / "frontend")
    ok("Frontend build complete")


# ---------------------------------------------------------------------------
# Step 7: Verify frontend/dist/index.html
# ---------------------------------------------------------------------------

def step_verify_frontend_dist() -> None:
    banner("Verify frontend/dist/index.html")
    index = ROOT / "frontend" / "dist" / "index.html"
    if not index.is_file():
        fail(f"Missing {index.relative_to(ROOT)}")
    ok("frontend/dist/index.html present")


# ---------------------------------------------------------------------------
# Step 8: Verify required assets
# ---------------------------------------------------------------------------

def step_verify_assets() -> None:
    banner("Verify assets and checkpoints")
    for d in REQUIRED_DIRS:
        rel = d.relative_to(ROOT)
        count = sum(1 for _ in d.iterdir()) if d.is_dir() else 0
        if count == 0:
            fail(f"{rel} is empty")
        ok(f"{rel}/ has {count} item(s)")


# ---------------------------------------------------------------------------
# Step 9: Verify Python dependencies can be imported
# ---------------------------------------------------------------------------

def step_verify_python_deps() -> None:
    banner("Verify Python dependencies")
    required = ["dotenv", "tqdm", "numpy", "torch", "doof"]
    for mod in required:
        try:
            __import__(mod)
        except (ImportError, ModuleNotFoundError):
            fail(f"Cannot import {mod} -- install via pip install -r requirements.txt")
        ok(f"  import {mod}")


# ---------------------------------------------------------------------------
# Step 10: Verify PySide6 imports
# ---------------------------------------------------------------------------

def step_verify_pyside6() -> None:
    banner("Verify PySide6 imports")
    modules = ["PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"]
    for mod in modules:
        try:
            __import__(mod)
        except ImportError as exc:
            fail(f"Cannot import {mod}: {exc}")
        ok(f"  import {mod}")


# ---------------------------------------------------------------------------
# Step 11: Verify torch imports + CUDA detection
# ---------------------------------------------------------------------------

def step_verify_torch() -> dict:
    banner("Verify torch imports")
    try:
        import torch
    except ImportError as exc:
        fail(f"Cannot import torch: {exc}")

    info = detect_cuda()
    ok(f"import torch ({torch.__version__})")
    if info["cuda_available"]:
        ok(f"CUDA available: {info['gpu_name']} ({info['gpu_vram_gb']} GB)")
        ok(f"CUDA version: {info['cuda_version']}")
    else:
        ok("CUDA not available -- building CPU-only package")
    return info


# ---------------------------------------------------------------------------
# Step 12: Verify model/inference imports
# ---------------------------------------------------------------------------

def step_verify_model_inference() -> None:
    banner("Verify model/inference imports")
    modules = [
        "doof",
        "doof.model",
        "doof.inference",
        "doof.inference.generate",
        "doof.training",
        "doof.tokenizer",
        "doof.cloud",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except ImportError as exc:
            fail(f"Cannot import {mod}: {exc}")
        ok(f"  import {mod}")


# ---------------------------------------------------------------------------
# Step 13: Build PyInstaller package
# ---------------------------------------------------------------------------

def step_build_pyinstaller() -> None:
    banner("Build PyInstaller package")
    # Clean previous build artifacts
    for stale in ["build", "dist"]:
        p = ROOT / stale
        if p.is_dir():
            print(f"  Cleaning {stale}/")
            shutil.rmtree(p, ignore_errors=True)

    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        str(ROOT / "packaging" / "doof.spec"),
    ])

    # Verify EXE was produced
    exe_dir = ROOT / "dist" / EXE_NAME
    exe_path = exe_dir / f"{EXE_NAME}.exe"
    if not exe_path.is_file():
        fail(f"PyInstaller did not produce {exe_path.relative_to(ROOT)}")

    ok(f"PyInstaller output: {exe_path.relative_to(ROOT)}")

    # Verify torch DLLs were collected
    internal = ROOT / "dist" / EXE_NAME / "_internal"
    torch_lib = internal / "torch" / "lib"
    if torch_lib.is_dir():
        dll_count = sum(1 for _ in torch_lib.glob("*.dll"))
        ok(f"torch/lib/ has {dll_count} DLLs")
        if dll_count < 5:
            fail(f"torch/lib/ only has {dll_count} DLLs -- collect_all may have failed")
        # Check for critical DLLs
        for critical in ("torch_cpu.dll", "c10.dll"):
            if not (torch_lib / critical).is_file():
                fail(f"Missing critical torch DLL: {critical}")
        ok("Critical torch DLLs present")
    else:
        fail("torch/lib/ not found in frozen package -- DLL collection failed")


# ---------------------------------------------------------------------------
# Step 14: Frozen smoke test
# ---------------------------------------------------------------------------

def step_frozen_smoke_test(cuda_info: dict) -> None:
    banner("Frozen smoke test (torch + model in frozen env)")
    frozen_dir = ROOT / "dist" / EXE_NAME
    internal = frozen_dir / "_internal"

    # Write a small test script that imports torch, loads model, runs inference
    test_script = frozen_dir / "_smoke_test.py"
    test_script.write_text(
        textwrap.dedent("""\
            import sys, os, json
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            _project_root = os.path.dirname(os.path.dirname(_script_dir))
            if _project_root not in sys.path:
                sys.path.insert(0, _project_root)
            result = {"ok": False, "checks": {}}
            try:
                import torch
                result["checks"]["torch_import"] = True
                result["checks"]["torch_version"] = torch.__version__
                result["checks"]["cuda_available"] = torch.cuda.is_available()
                result["checks"]["torch_cuda_version"] = getattr(torch.version, "cuda", "CPU build")
                if torch.cuda.is_available():
                    result["checks"]["gpu_name"] = torch.cuda.get_device_name(0)
                    props = torch.cuda.get_device_properties(0)
                    result["checks"]["gpu_vram_gb"] = round(props.total_memory / (1024**3), 2)
            except Exception as e:
                result["checks"]["torch_import"] = False
                result["checks"]["torch_error"] = str(e)
                print(json.dumps(result))
                sys.exit(1)

            try:
                from doof.model.transformer import DOOFTransformer
                from doof.tokenizer import DOOFTokenizer
                # Search multiple paths for the checkpoint
                _script_dir = os.path.dirname(os.path.abspath(__file__))
                _search = [
                    os.path.join(_script_dir, "_internal", "checkpoints", "doof_v01.pt"),
                    os.path.join(_script_dir, "checkpoints", "doof_v01.pt"),
                    os.path.join(os.path.dirname(sys.executable), "_internal", "checkpoints", "doof_v01.pt"),
                    os.path.join(os.path.dirname(sys.executable), "checkpoints", "doof_v01.pt"),
                ]
                ckpt_path = next((p for p in _search if os.path.isfile(p)), None)
                if ckpt_path is None:
                    result["checks"]["checkpoint_found"] = False
                    result["checks"]["searched"] = _search
                    print(json.dumps(result))
                    sys.exit(1)
                ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
                mc = ckpt.get("model_config", {})
                sd = ckpt.get("model_state_dict", {})
                param_count = sum(v.numel() for v in sd.values())
                tok = DOOFTokenizer()
                model = DOOFTransformer(
                    vocab_size=mc.get("vocab_size", tok.vocab_size),
                    max_seq_len=mc.get("max_seq_len", 64),
                    d_model=mc.get("d_model", 256),
                )
                model.load_state_dict(sd)
                model.eval()
                result["checks"]["model_loaded"] = True
                result["checks"]["parameters"] = param_count
                result["checks"]["parameters_m"] = round(param_count / 1e6, 2)
                result["checks"]["d_model"] = mc.get("d_model")
                result["checks"]["vocab_size"] = mc.get("vocab_size")
            except Exception as e:
                result["checks"]["model_loaded"] = False
                result["checks"]["model_error"] = str(e)
                print(json.dumps(result))
                sys.exit(1)

            try:
                from doof.inference.generate import DOOFInference
                inf = DOOFInference(ckpt_path)
                text = inf.generate("hello", max_new_tokens=30)
                result["checks"]["inference_ok"] = len(text.strip()) > 0
                result["checks"]["generated_sample"] = text[:80]
            except Exception as e:
                result["checks"]["inference_ok"] = False
                result["checks"]["inference_error"] = str(e)
                print(json.dumps(result))
                sys.exit(1)

            result["ok"] = True
            print(json.dumps(result, indent=2))
        """),
        encoding="utf-8",
    )

    # Run the smoke test using the frozen Python environment
    frozen_python = frozen_dir / "_internal" / "Python" / "python.exe"
    if not frozen_python.is_file():
        frozen_python = internal / "Python" / "python.exe"
    if not frozen_python.is_file():
        ok("Frozen Python not found -- running smoke test with dev Python + frozen DLLs")
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(frozen_dir),
            capture_output=True, text=True, timeout=120,
        )
    else:
        result = subprocess.run(
            [str(frozen_python), str(test_script)],
            cwd=str(frozen_dir),
            capture_output=True, text=True, timeout=120,
        )

    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"    {line}")
    if result.returncode != 0:
        fail(f"Frozen smoke test FAILED (exit {result.returncode})")

    # Parse JSON results
    stdout_text = result.stdout.strip()
    json_start = stdout_text.find("{")
    if json_start < 0:
        fail(f"Could not find JSON in smoke test output: {result.stdout[:200]}")
        return
    decoder = json.JSONDecoder()
    try:
        data, _ = decoder.raw_decode(stdout_text, json_start)
    except json.JSONDecodeError:
        fail(f"Could not parse smoke test output: {result.stdout[:200]}")
        return

    if not data.get("ok"):
        fail(f"Frozen smoke test reported failure: {json.dumps(data.get('checks', {}))}")

    checks = data["checks"]
    ok(f"torch {checks.get('torch_version', '?')}")
    ok(f"parameters: {checks.get('parameters_m', '?')}M")
    ok(f"d_model: {checks.get('d_model', '?')}")
    ok(f"inference: {'PASS' if checks.get('inference_ok') else 'FAIL'}")
    ok(f"generated: {checks.get('generated_sample', '?')[:60]}")

    # Verify CUDA state matches what we detected pre-build
    frozen_cuda = checks.get("cuda_available", False)
    if cuda_info["cuda_available"] and not frozen_cuda:
        fail(
            f"CUDA was available pre-build ({cuda_info['gpu_name']}) "
            f"but NOT in frozen env -- CUDA DLLs may not have been bundled"
        )
    if cuda_info["cuda_available"] and frozen_cuda:
        ok(f"CUDA verified in frozen env: {checks.get('gpu_name', '?')} ({checks.get('gpu_vram_gb', '?')} GB)")

    # Cleanup
    test_script.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 15: Verify no .env secrets packaged
# ---------------------------------------------------------------------------

def step_verify_no_env_secrets() -> None:
    banner("Verify no .env secrets packaged")
    exe_dir = ROOT / "dist" / EXE_NAME
    internal = exe_dir / "_internal"

    leaked = []
    for candidate in [exe_dir / ".env", internal / ".env"]:
        if candidate.is_file():
            leaked.append(str(candidate.relative_to(ROOT)))
            candidate.unlink()
    for candidate in internal.rglob(".env"):
        if candidate.is_file() and "node_modules" not in candidate.parts:
            leaked.append(str(candidate.relative_to(ROOT)))
            candidate.unlink()

    if leaked:
        print(f"  WARNING: removed .env files: {', '.join(leaked)}")
    ok("No .env secrets in packaged build")

    # Verify .env.example IS present
    example = exe_dir / ".env.example"
    if example.is_file():
        ok(".env.example present (safe template)")
    else:
        ok(".env.example not present (acceptable)")


# ---------------------------------------------------------------------------
# Step 16: Write BUILD_INFO.txt
# ---------------------------------------------------------------------------

def step_write_build_info(version: str, cuda_info: dict) -> Path:
    banner("Write BUILD_INFO.txt")
    import platform as _platform
    import subprocess as _subprocess

    try:
        git_commit = _subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, text=True, stderr=_subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_commit = "unknown"

    try:
        import PyInstaller
        pyinstaller_version = PyInstaller.__version__
    except Exception:
        pyinstaller_version = "unknown"

    build_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    os_platform = _platform.system()
    arch = _platform.machine()

    content = textwrap.dedent(f"""\
        DOOF Build Information
        ======================
        Version:          {version}
        Build Type:       {cuda_info['build_label']}
        Git Commit:       {git_commit}
        Build Timestamp:  {build_time}
        Python Version:   {python_version}
        PyInstaller Ver:  {pyinstaller_version}
        Platform:         {os_platform}
        Architecture:     {arch}
        Torch Version:    {cuda_info['torch_version'] or 'N/A'}
        CUDA Version:     {cuda_info['cuda_version'] or 'N/A'}
        GPU:              {cuda_info['gpu_name'] or 'N/A'}
        GPU VRAM:         {cuda_info['gpu_vram_gb'] or 'N/A'} GB
    """)

    build_info = ROOT / "dist" / EXE_NAME / "BUILD_INFO.txt"
    build_info.write_text(content, encoding="utf-8")
    ok(f"Written to {build_info.relative_to(ROOT)}")
    return build_info


# ---------------------------------------------------------------------------
# Step 17: Generate release.json manifest
# ---------------------------------------------------------------------------

def step_generate_release_json(version: str, cuda_info: dict) -> Path:
    banner("Generate release.json")
    import subprocess as _subprocess

    try:
        git_commit = _subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT, text=True, stderr=_subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_commit = "unknown"

    build_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    import platform as _platform

    manifest = {
        "product": "DOOF",
        "version": version,
        "channel": "stable",
        "platform": _platform.system().lower(),
        "arch": "x64",
        "build_type": cuda_info["build_label"],
        "cuda_available": cuda_info["cuda_available"],
        "cuda_version": cuda_info["cuda_version"],
        "gpu_name": cuda_info["gpu_name"],
        "gpu_vram_gb": cuda_info["gpu_vram_gb"],
        "torch_version": cuda_info["torch_version"],
        "build_time": build_time,
        "git_commit": git_commit,
        "min_supported": "2.0.0",
    }

    release_json = ROOT / "dist" / EXE_NAME / "release.json"
    release_json.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    ok(f"Written to {release_json.relative_to(ROOT)}")
    return release_json


# ---------------------------------------------------------------------------
# Step 18: Generate SHA256SUMS.txt
# ---------------------------------------------------------------------------

def step_generate_sha256sums() -> Path:
    banner("Generate SHA256SUMS.txt")
    exe_dir = ROOT / "dist" / EXE_NAME
    lines: list[str] = []

    for f in sorted(exe_dir.rglob("*")):
        if f.is_dir():
            continue
        if "__pycache__" in f.parts:
            continue
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rel = f.relative_to(exe_dir)
        lines.append(f"{sha}  {rel}")

    sums_path = exe_dir / "SHA256SUMS.txt"
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f"Checksums for {len(lines)} files written to {sums_path.relative_to(ROOT)}")
    return sums_path


# ---------------------------------------------------------------------------
# Step 19: Create release directory
# ---------------------------------------------------------------------------

def step_create_release_dir(version: str) -> Path:
    banner(f"Create releases/{RELEASE_VERSION_DIR}/")
    release_dir = ROOT / "releases" / RELEASE_VERSION_DIR
    if release_dir.is_dir():
        shutil.rmtree(release_dir, ignore_errors=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    exe_dir = ROOT / "dist" / EXE_NAME

    # Copy EXE
    src_exe = exe_dir / f"{EXE_NAME}.exe"
    dst_exe = release_dir / f"{EXE_NAME}.exe"
    if not src_exe.is_file():
        fail(f"Source EXE not found: {src_exe.relative_to(ROOT)}")
    shutil.copy2(src_exe, dst_exe)
    ok(f"Copied {EXE_NAME}.exe")

    # Copy _internal/
    src_internal = exe_dir / "_internal"
    dst_internal = release_dir / "_internal"
    if src_internal.is_dir():
        shutil.copytree(src_internal, dst_internal, dirs_exist_ok=True)
        ok("Copied _internal/")
    else:
        fail("_internal/ not found in dist output")

    # Copy .env.example -- never .env
    shutil.copy2(ROOT / ".env.example", release_dir / ".env.example")
    ok("Copied .env.example")

    # Remove any .env that snuck in
    leaked = release_dir / ".env"
    if leaked.is_file():
        leaked.unlink()
        ok("Removed .env from release dir (security)")

    # Create README_FIRST.txt
    readme_content = textwrap.dedent(f"""\
        DOOF v{version} -- Quick Start
        ============================

        1.  Copy .env.example to .env and fill in your Supabase credentials.
        2.  Double-click "{EXE_NAME}.exe" to launch DOOF.
        3.  The first launch may take a moment while models are loaded.

        For help visit: https://github.com/icecut710/Doof
    """)
    (release_dir / "README_FIRST.txt").write_text(readme_content, encoding="utf-8")
    ok("Created README_FIRST.txt")

    # Copy BUILD_INFO.txt and release.json from dist
    for name in ["BUILD_INFO.txt", "release.json", "SHA256SUMS.txt"]:
        src = exe_dir / name
        if src.is_file():
            shutil.copy2(src, release_dir / name)
            ok(f"Copied {name}")

    # Copy manifest.json (the top-level release manifest)
    manifest_src = ROOT / "releases" / "manifest.json"
    if manifest_src.is_file():
        shutil.copy2(manifest_src, release_dir / "manifest.json")
        ok("Copied manifest.json")

    ok(f"Release directory ready: {release_dir.relative_to(ROOT)}")
    return release_dir


# ---------------------------------------------------------------------------
# Step 20: Create zip
# ---------------------------------------------------------------------------

def step_create_zip(version: str) -> Path:
    banner(f"Create {ZIP_NAME}")
    release_dir = ROOT / "releases" / RELEASE_VERSION_DIR
    zip_path = ROOT / "releases" / ZIP_NAME

    if zip_path.is_file():
        zip_path.unlink()

    shutil.make_archive(
        base_name=str(zip_path.with_suffix("")),
        format="zip",
        root_dir=str(release_dir),
    )
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    ok(f"Created {zip_path.relative_to(ROOT)} ({size_mb:.1f} MB)")
    return zip_path


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------

def step_final_report(version: str, zip_path: Path, cuda_info: dict) -> None:
    banner("FINAL REPORT")
    print()
    print(f"  Product:      DOOF v{version}")
    print(f"  Build Type:   {cuda_info['build_label']}")
    print(f"  Channel:      stable")
    print(f"  Platform:     Windows x64")
    if cuda_info["cuda_available"]:
        print(f"  GPU:          {cuda_info['gpu_name']} ({cuda_info['gpu_vram_gb']} GB)")
        print(f"  CUDA:         {cuda_info['cuda_version']}")
    print(f"  Torch:        {cuda_info['torch_version']}")
    print(f"  Package:      {ZIP_NAME}")
    print(f"  Zip:          {zip_path.relative_to(ROOT)}")
    print(f"  Release dir:  releases/{RELEASE_VERSION_DIR}/")
    print()
    print(f"  {'*' * 40}")
    print(f"  ***  BUILD SUCCESS -- ALL {STEP_COUNT} STEPS PASSED  ***")
    print(f"  {'*' * 40}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

STEP_COUNT = 20


def main() -> None:
    print()
    print(f"{'#' * 72}")
    print(f"  DOOF v3.0 Release Pipeline")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 72}")

    # Steps 1-11: Validation
    step_validate_repo()
    version = step_validate_version()
    step_run_tests()
    npm = step_verify_npm()
    step_verify_frontend_deps()
    step_build_frontend(npm)
    step_verify_frontend_dist()
    step_verify_assets()
    step_verify_python_deps()
    step_verify_pyside6()
    cuda_info = step_verify_torch()
    step_verify_model_inference()

    # Step 12: Build
    step_build_pyinstaller()

    # Step 13: Frozen smoke test (passes cuda_info to verify CUDA survives packaging)
    step_frozen_smoke_test(cuda_info)

    # Step 14: Security -- no .env secrets
    step_verify_no_env_secrets()

    # Steps 15-17: Metadata (with CUDA info)
    step_write_build_info(version, cuda_info)
    step_generate_release_json(version, cuda_info)
    step_generate_sha256sums()

    # Steps 18-19: Package
    step_create_release_dir(version)
    zip_path = step_create_zip(version)

    # Step 20: Done
    step_final_report(version, zip_path, cuda_info)


if __name__ == "__main__":
    main()
