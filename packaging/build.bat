@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo.
echo  ============================================
echo   DOOF v3.0 - build
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

REM Detect CUDA torch — NEVER uninstall a working CUDA install.
python -c "import torch; assert torch.cuda.is_available()" 2>nul
if errorlevel 1 (
  echo [build] CUDA torch not detected. Building CPU-only package.
  echo [build] To build with GPU support, install CUDA torch first:
  echo [build]   pip install torch --index-url https://download.pytorch.org/whl/cu128
) else (
  echo [build] CUDA torch detected — packaging GPU-enabled build.
)

echo [build] Running packaging\build_exe.py ...
python packaging\build_exe.py
if errorlevel 1 (
  echo.
  echo [ERROR] Build failed. Scroll up for the first error.
  exit /b 1
)

echo.
echo  DONE. Output: dist\Doof v3.0\Doof v3.0.exe
echo  Read:         dist\Doof v3.0\README_FIRST.txt
echo  Zip the whole dist\Doof v3.0 folder (EXE + _internal) to share.
echo.
exit /b 0
