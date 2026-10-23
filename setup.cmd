@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
  echo Setup did not finish. See the error above.
  pause
  exit /b 1
)
echo Setup complete. Double-click start.cmd to open the website.
pause
