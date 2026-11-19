@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ENABLE_MT5_DEMO_PERMISSIONS.ps1"
echo.
echo Close this window after reviewing the output.
pause
