@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ready
py -3 -m venv .venv
if errorlevel 1 goto fail
:ready
".venv\Scripts\python.exe" bootstrap.py
if errorlevel 1 goto fail
pause
exit /b 0
:fail
echo Startup failed. Check the error above. Python 3.11 or later and network access are required for installation.
echo Existing data, images and tasks have been preserved.
pause
exit /b 1
