# AI Coding Tool - 快速启动脚本

echo "🚀 启动 AI Coding Tool 后端服务..."
echo ""

# 进入后端目录
cd "$(dirname "$0")/backend"

# 启动服务
echo ""
echo "✅ 启动 FastAPI 服务..."
echo "📍 地址: http://localhost:5500"
echo "💾 数据库: ~/vscode_chat.db"
echo ""
echo "按 Ctrl+C 停止服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 app_fastapi.py