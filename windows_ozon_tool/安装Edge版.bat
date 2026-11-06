@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installed. Run start_edge.bat
pause
exit /b 0
:fail
echo Installation failed. Python 3.11 or later required.
pause
exit /b 1
