@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto repair
py -3 -m venv .venv
if errorlevel 1 goto fail
:repair
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --prefer-binary -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" bootstrap.py --check-only
if errorlevel 1 goto fail
echo Dependencies ready. Run start_edge.bat again.
pause
exit /b 0
:fail
echo Repair failed. Check the error above. Existing data has been preserved.
pause
exit /b 1
