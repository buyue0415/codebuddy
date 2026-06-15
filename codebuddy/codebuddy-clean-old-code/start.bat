@echo off
chcp 65001 >nul
title 股票投资管理系统 V2 (FastAPI)

echo ============================================
echo   股票投资管理系统 V2 - FastAPI 版
echo ============================================
echo.
echo   后端: FastAPI (端口 8766)
echo   前端: Vite (端口 5173)
echo.
echo   API 文档: http://localhost:8766/docs
echo   Swagger:  http://localhost:8766/docs
echo.

:: Start FastAPI backend
echo [1/2] 启动 FastAPI 后端 (端口 8766)...
start "FastAPI" /min C:\Users\28312\AppData\Local\Programs\Python\Python312\python.exe server_v2.py
timeout /t 3 /nobreak >nul

:: Start Vite frontend
echo [2/2] 启动前端 Vite (端口 5173)...
echo.
cd /d "%~dp0deliverables\v2"
start http://localhost:5173
npx vite --host

pause
