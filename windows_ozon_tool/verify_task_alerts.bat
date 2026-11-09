@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" verify_task_alerts.py --demo
) else (
 py -3 verify_task_alerts.py --demo
)
if errorlevel 1 (
 echo 本地验证未完成，请复制错误信息。请先完成工具依赖安装。
 pause
 exit /b 1
)
pause
exit /b 0
