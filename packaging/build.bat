@echo off
setlocal
cd /d "%~dp0.."

echo === DOOF v0.2 packaging ===

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found on PATH
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm not found on PATH
  exit /b 1
)

python -m pip install -q pyinstaller
python packaging\build_exe.py
if errorlevel 1 exit /b 1

echo.
echo ZIP for friends (optional):
echo   powershell Compress-Archive -Path dist\DOOF -DestinationPath dist\DOOF-v0.2-windows.zip -Force
echo.
echo Friend flow: extract ZIP -^> double-click DOOF.exe
endlocal
