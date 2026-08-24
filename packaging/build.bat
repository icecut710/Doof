@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo.
echo  ============================================
echo   DOOF v0.3 — friend-ready onedir build
echo  ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] python not on PATH. Install Python 3.11+ and retry.
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not on PATH. Install Node.js 18+ and retry.
  exit /b 1
)

python -c "import PySide6" 2>nul
if errorlevel 1 (
  echo [build] Installing Python deps (PySide6, PyInstaller, ...)
  python -m pip install -U pip
  python -m pip install -r requirements.txt
  python -m pip install pyinstaller python-dotenv
)

REM Friend builds default to CPU torch (~600-800MB) instead of CUDA (~5GB).
REM Owner GPU builds: set DOOF_KEEP_CUDA=1 before running this script,
REM and ensure a CUDA torch wheel is already installed in the venv.
if defined DOOF_KEEP_CUDA (
  echo [build] DOOF_KEEP_CUDA=1 — keeping existing torch (use CUDA wheel for GPU EXE)
) else (
  echo [build] Installing CPU-only torch for a shareable EXE
  python -m pip uninstall -y torch
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
)

echo [build] Running packaging\build_exe.py ...
python packaging\build_exe.py
if errorlevel 1 (
  echo.
  echo [ERROR] Build failed. Scroll up for the first error.
  exit /b 1
)

echo.
echo  DONE. Output: dist\DOOF\DOOF.exe
echo  Read:         dist\DOOF\README_FIRST.txt
echo  Zip the whole dist\DOOF folder (EXE + _internal) to share.
echo  GPU owner rebuild: set DOOF_KEEP_CUDA=1 and install cu124 torch first.
echo.
exit /b 0
