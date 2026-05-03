#!/bin/bash
# AI Coding Tool - Mac 完整打包脚本（后端 + VSCode 插件）

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# 切换到项目根目录
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "  AI Coding Tool - Mac 完整打包"
echo "=========================================="
echo "📍 工作目录: $(pwd)"
echo ""

# 步骤 1: 打包后端
echo "📦 步骤 1/3: 打包后端..."
echo "=========================================="

# 清理旧的打包文件
echo "🧹 清理旧的打包文件..."
rm -rf build dist backend-bin

# 运行 PyInstaller
echo "⚙️  开始打包后端..."
uv run pyinstaller backend.spec

# 创建输出目录
mkdir -p backend-bin

# 移动可执行文件
if [ -f "dist/backend" ]; then
    mv dist/backend backend-bin/
    chmod +x backend-bin/backend
    echo "✅ 后端打包完成！"
    echo "📍 可执行文件位置: backend-bin/backend"
    ls -lh backend-bin/backend
else
    echo "❌ 后端打包失败，未找到可执行文件"
    exit 1
fi

# 清理临时文件
echo "🧹 清理临时文件..."
rm -rf build dist

echo ""

# 步骤 2: 编译 TypeScript
echo "📦 步骤 2/3: 编译 TypeScript..."
echo "=========================================="
npm run compile
echo "✅ TypeScript 编译完成！"
echo ""

# 步骤 3: 打包 VSCode 插件
echo "📦 步骤 3/3: 打包 VSCode 插件..."
echo "=========================================="

# 删除旧的 .vsix 文件
rm -f *.vsix

# 运行 vsce package
vsce package

echo ""
echo "=========================================="
echo "  ✅ 打包完成！"
echo "=========================================="
echo ""
echo "📦 生成的文件："
echo "  - backend-bin/backend (后端可执行文件)"
ls -1 *.vsix 2>/dev/null | while read file; do
    echo "  - $file (VSCode 插件)"
    ls -lh "$file"
done
echo ""
echo "💡 安装插件："
echo "   code --install-extension *.vsix"
echo ""
