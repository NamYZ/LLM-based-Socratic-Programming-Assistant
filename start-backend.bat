@echo off
REM AI Coding Tool - Windows 启动脚本

echo 🚀 启动 AI Coding Tool 后端服务...
echo.

REM 进入后端目录
cd /d "%~dp0backend"

REM 启动服务
echo.
echo ✅ 启动 FastAPI 服务...
echo 📍 地址: http://localhost:5500
echo 💾 数据库: %USERPROFILE%\vscode_chat.db
echo.
echo 按 Ctrl+C 停止服务
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

python app_fastapi.py
