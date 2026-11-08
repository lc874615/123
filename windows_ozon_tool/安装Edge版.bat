@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3 -m venv .venv
if errorlevel 1 goto fail
:install
".venv\Scripts\python.exe" bootstrap.py --check-only
if errorlevel 1 goto fail
echo Dependencies ready. Run start_edge.bat
pause
exit /b 0
:fail
echo Installation failed. Check the error above. Python 3.11 or later required.
echo Existing data, images and tasks have been preserved.
pause
exit /b 1
