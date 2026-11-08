@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3 -m venv .venv
if errorlevel 1 goto fail
:install
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" bootstrap.py --check-only
if errorlevel 1 goto fail
echo Installed. Run start_edge.bat
pause
exit /b 0
:fail
echo Installation failed. Python 3.11 or later required.
pause
exit /b 1
