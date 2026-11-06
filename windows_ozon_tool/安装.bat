@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto fail
echo Installation complete.
pause
exit /b 0
:fail
echo Installation failed. Install Python 3.11 or later and try again.
pause
exit /b 1
