@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python 3.10+ is required. Run setup.cmd first.
    pause
    exit /b 1
  )
  py -3 app.py
  if errorlevel 1 pause
  exit /b %errorlevel%
)
python app.py
if errorlevel 1 pause
