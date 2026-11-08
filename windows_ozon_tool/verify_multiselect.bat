@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" verify_multiselect.py
) else (
 py -3 verify_multiselect.py
)
if errorlevel 1 (
 echo.
 echo 本地验证未通过，请复制窗口中的错误信息。请先完成本地工具依赖安装。
 pause
 exit /b 1
)
pause
exit /b 0
