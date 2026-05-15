@echo off
chcp 65001 > nul
title 题库管理系统 - 后端
echo ========================================
echo  小升初数学题库管理系统 v4.0
echo  正在启动后端服务...
echo ========================================
echo.

setlocal enabledelayedexpansion

:: Check if .env file exists and load DEEPSEEK_API_KEY
if exist "%~dp0backend\.env" (
    for /f "tokens=*" %%a in (%~dp0backend\.env) do (
        set "%%a"
    )
)

cd /d "%~dp0backend"
python run.py
pause