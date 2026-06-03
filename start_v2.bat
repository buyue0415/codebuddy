@echo off
chcp 65001 >nul
title 股票投资管理系统 V2

echo ============================================
echo   股票投资管理系统 V2
echo ============================================
echo.

:: Start Python backend
echo [1/2] 启动后端 API (端口 8765)...
start "Backend" /min python server.py
timeout /t 4 /nobreak >nul

echo [2/2] 启动前端 Vite (端口 5173)...
echo.
cd /d "%~dp0deliverables\v2"
start http://localhost:5173
npx vite --host

pause
