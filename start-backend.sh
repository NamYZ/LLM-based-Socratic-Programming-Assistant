# AI Coding Tool - 快速启动脚本

echo "🚀 启动 AI Coding Tool 后端服务..."
echo ""

# 禁用 Python 字节码生成
export PYTHONDONTWRITEBYTECODE=1

# 清理旧的 __pycache__ 目录
echo "🧹 清理 __pycache__ 目录..."
find "$(dirname "$0")/backend" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find "$(dirname "$0")/backend" -type f -name "*.pyc" -delete 2>/dev/null
echo "✅ 清理完成"
echo ""

# 进入后端目录
cd "$(dirname "$0")/backend"

# 启动服务
echo "✅ 启动 FastAPI 服务..."
echo "📍 地址: http://localhost:5500"
echo "💾 数据库: ~/vscode_chat.db"
echo "🚫 已禁用 __pycache__ 生成"
echo ""
echo "按 Ctrl+C 停止服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 app_fastapi.py
