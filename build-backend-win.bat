@echo off
REM AI Coding Tool - Windows 后端打包脚本

echo 🚀 开始打包 Windows 后端...
echo.

REM 检查是否安装了 uv
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 未找到 uv，请先安装: https://github.com/astral-sh/uv
    exit /b 1
)

REM 检查是否安装了 PyInstaller
echo 📦 检查 PyInstaller...
uv pip list | findstr /C:"pyinstaller" >nul
if %ERRORLEVEL% NEQ 0 (
    echo 📥 安装 PyInstaller...
    uv pip install pyinstaller
)

REM 清理旧的打包文件
echo 🧹 清理旧的打包文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist backend-bin rmdir /s /q backend-bin

REM 运行 PyInstaller
echo ⚙️  开始打包...
uv run pyinstaller backend.spec

REM 创建输出目录
mkdir backend-bin

REM 移动可执行文件
if exist "dist\backend.exe" (
    move "dist\backend.exe" "backend-bin\"
    echo ✅ 打包完成！
    echo 📍 可执行文件位置: backend-bin\backend.exe

    REM 显示文件大小
    dir backend-bin\backend.exe
) else (
    echo ❌ 打包失败，未找到可执行文件
    exit /b 1
)

REM 清理临时文件
echo 🧹 清理临时文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo ✅ Windows 后端打包完成！
echo 💡 提示：现在可以运行 'vsce package' 打包 VSCode 插件
