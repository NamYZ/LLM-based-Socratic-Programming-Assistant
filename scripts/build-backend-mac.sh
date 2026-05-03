#!/bin/bash
# AI Coding Tool - Mac 后端打包脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# 切换到项目根目录
cd "$SCRIPT_DIR/.."

echo "🚀 开始打包 Mac 后端..."
echo "📍 工作目录: $(pwd)"
echo ""

# 清理旧的打包文件
echo "🧹 清理旧的打包文件..."
rm -rf build dist backend-bin

# 运行 PyInstaller
echo "⚙️  开始打包..."
uv run pyinstaller backend.spec

# 创建输出目录
mkdir -p backend-bin

# 移动可执行文件
if [ -f "dist/backend" ]; then
    mv dist/backend backend-bin/
    echo "✅ 打包完成！"
    echo "📍 可执行文件位置: backend-bin/backend"

    # 设置执行权限
    chmod +x backend-bin/backend

    # 显示文件大小
    ls -lh backend-bin/backend
else
    echo "❌ 打包失败，未找到可执行文件"
    exit 1
fi

# 清理临时文件
echo "🧹 清理临时文件..."
rm -rf build dist

echo ""
echo "✅ Mac 后端打包完成！"
echo "💡 提示：现在可以运行 'vsce package' 打包 VSCode 插件"
