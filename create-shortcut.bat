@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (echo Run install.bat first.& pause& exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'VoiceForge.lnk'));$s.TargetPath='%CD%\.venv\Scripts\pythonw.exe';$s.Arguments='""%CD%\launcher.pyw""';$s.WorkingDirectory='%CD%';$s.IconLocation='%CD%\voiceforge.ico';$s.Save()"
if errorlevel 1 (echo Could not create shortcut.& pause& exit /b 1)
echo VoiceForge shortcut created on your Desktop.
pause
