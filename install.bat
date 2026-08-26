@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10-3.12 is required.& pause & exit /b 1)
where ffmpeg >nul 2>nul || (echo ffmpeg and ffprobe must be on PATH. See README.md.& pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv .venv || exit /b 1
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements\core.txt || (pause & exit /b 1)
echo Core installation complete. Lip-sync is optional; see docs\optional-lipsync.md.
pause
