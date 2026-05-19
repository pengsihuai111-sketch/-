@echo off
chcp 65001 > nul
echo 正在停止所有占用 8000 端口的进程...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    echo 停止进程 PID: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo 所有进程已停止
echo.
echo 现在启动后端服务器...
cd /d "%~dp0"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
