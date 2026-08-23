@echo off
REM DOOF v0.2 Alpha — Windows Build Script
REM Run from the project root: packaging\build.bat

echo [DOOF Build] Starting...
echo.

REM 1. Build frontend
echo [1/3] Building frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed.
    pause
    exit /b 1
)
cd ..
echo [1/3] Frontend built.
echo.

REM 2. Install PyInstaller if needed
echo [2/3] Checking PyInstaller...
python -m pip install pyinstaller --quiet
echo [2/3] PyInstaller ready.
echo.

REM 3. Run PyInstaller
echo [3/3] Building EXE...
python packaging\build_exe.py
if errorlevel 1 (
    echo [ERROR] EXE build failed.
    pause
    exit /b 1
)

echo.
echo [DOOF Build] Complete!
echo EXE is in: dist\DOOF\DOOF.exe
echo.
pause
