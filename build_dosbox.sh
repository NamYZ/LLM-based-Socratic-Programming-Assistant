#!/bin/bash
# DOSBox 编译脚本

set -e  # 遇到错误立即退出

echo "=========================================="
echo "DOSBox 编译脚本"
echo "=========================================="

# 进入 DOSBox 目录
cd "$(dirname "$0")/dosbox-code-0-r4494-dosbox-trunk"

echo ""
echo "步骤 1: 检查依赖..."
if ! command -v autoconf &> /dev/null; then
    echo "❌ autoconf 未安装"
    echo "请运行: brew install autoconf automake (macOS) 或 sudo apt-get install autoconf automake (Linux)"
    exit 1
fi

if ! command -v sdl-config &> /dev/null; then
    echo "❌ SDL 未安装"
    echo "请运行: brew install sdl sdl_net sdl_sound (macOS) 或 sudo apt-get install libsdl1.2-dev (Linux)"
    exit 1
fi

echo "✅ 依赖检查通过"

echo ""
echo "步骤 2: 生成配置脚本..."
./autogen.sh

echo ""
echo "步骤 3: 配置..."
./configure --enable-debug

echo ""
echo "步骤 4: 编译..."
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

echo ""
echo "=========================================="
echo "✅ 编译完成！"
echo "=========================================="
echo ""
echo "可执行文件位于: src/dosbox"
echo ""
echo "测试命令:"
echo "  ./src/dosbox --version"
echo ""
echo "下一步:"
echo "  1. 运行测试: ./test_dosbox.sh"
echo "  2. 启动后端: cd backend && python app_fastapi.py"
echo "  3. 使用 VS Code 插件"
echo ""
