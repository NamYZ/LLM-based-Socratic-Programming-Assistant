@echo off
REM AI Coding Tool - Windows 完整打包脚本（后端 + VSCode 插件）

REM 切换到脚本所在目录的父目录（项目根目录）
cd /d "%~dp0.."

echo ==========================================
echo   AI Coding Tool - Windows 完整打包
echo ==========================================
echo 📍 工作目录: %CD%
echo.

REM 步骤 1: 打包后端
echo 📦 步骤 1/3: 打包后端...
echo ==========================================

REM 清理旧的打包文件
echo 🧹 清理旧的打包文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist backend-bin rmdir /s /q backend-bin

REM 运行 PyInstaller
echo ⚙️  开始打包后端...
uv run pyinstaller backend.spec

REM 创建输出目录
mkdir backend-bin

REM 移动可执行文件
if exist "dist\backend.exe" (
    move "dist\backend.exe" "backend-bin\"
    echo ✅ 后端打包完成！
    echo 📍 可执行文件位置: backend-bin\backend.exe
    dir backend-bin\backend.exe
) else (
    echo ❌ 后端打包失败，未找到可执行文件
    exit /b 1
)

REM 清理临时文件
echo 🧹 清理临时文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.

REM 步骤 2: 编译 TypeScript
echo 📦 步骤 2/3: 编译 TypeScript...
echo ==========================================
call npm run compile
echo ✅ TypeScript 编译完成！
echo.

REM 步骤 3: 打包 VSCode 插件
echo 📦 步骤 3/3: 打包 VSCode 插件...
echo ==========================================

REM 删除旧的 .vsix 文件
del /q *.vsix 2>nul

REM 运行 vsce package
call vsce package

echo.
echo ==========================================
echo   ✅ 打包完成！
echo ==========================================
echo.
echo 📦 生成的文件：
echo   - backend-bin\backend.exe (后端可执行文件)
for %%f in (*.vsix) do (
    echo   - %%f (VSCode 插件)
    dir %%f
)
echo.
echo 💡 安装插件：
echo    code --install-extension *.vsix
echo.
