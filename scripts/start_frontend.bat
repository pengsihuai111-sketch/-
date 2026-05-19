@echo off
chcp 65001 > nul
title 题库管理系统 - 前端
echo ========================================
echo  小升初数学题库管理系统 v4.0
echo  正在启动前端服务...
echo ========================================
echo.
cd /d "%~dp0frontend"
npm run dev
pause
