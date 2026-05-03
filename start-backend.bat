@echo off
REM AI Coding Tool - Windows 启动脚本

echo 🚀 启动 AI Coding Tool 后端服务...
echo.

REM 禁用 Python 字节码生成
set PYTHONDONTWRITEBYTECODE=1

REM 清理旧的 __pycache__ 目录
echo 🧹 清理 __pycache__ 目录...
for /d /r "%~dp0backend" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q "%~dp0backend\*.pyc" 2>nul
echo ✅ 清理完成
echo.

REM 进入后端目录
cd /d "%~dp0backend"

REM 启动服务
echo ✅ 启动 FastAPI 服务...
echo 📍 地址: http://localhost:5500
echo 💾 数据库: %USERPROFILE%\vscode_chat.db
echo 🚫 已禁用 __pycache__ 生成
echo.
echo 按 Ctrl+C 停止服务
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

python app_fastapi.py
