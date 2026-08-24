@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

echo.
echo  ============================================
echo   DOOF v0.2 — friend-ready onedir build
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
echo  Zip the whole dist\DOOF folder to share.
echo.
exit /b 0
