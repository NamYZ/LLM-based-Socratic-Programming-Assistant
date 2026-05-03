@echo off
REM AI Coding Tool - Windows 后端打包脚本

REM 切换到脚本所在目录的父目录（项目根目录）
cd /d "%~dp0.."

echo 🚀 开始打包 Windows 后端...
echo 📍 工作目录: %CD%
echo.

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
