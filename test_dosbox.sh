#!/bin/bash
# DOSBox Trace 功能测试脚本

set -e

echo "=========================================="
echo "DOSBox Trace 功能测试"
echo "=========================================="

# 检查 DOSBox 是否已编译
DOSBOX_PATH="./dosbox-code-0-r4494-dosbox-trunk/src/dosbox"
if [ ! -f "$DOSBOX_PATH" ]; then
    echo "❌ DOSBox 未找到，请先运行 ./build_dosbox.sh"
    exit 1
fi

# 检查 NASM
if ! command -v nasm &> /dev/null; then
    echo "❌ NASM 未安装"
    echo "请运行: brew install nasm (macOS) 或 sudo apt-get install nasm (Linux)"
    exit 1
fi

echo ""
echo "步骤 1: 创建测试汇编代码..."
mkdir -p /tmp/dosbox_test
cat > /tmp/dosbox_test/test.asm << 'EOF'
ORG 100h

MOV AX, 5
ADD AX, 3
MOV BX, AX
INT 20h
EOF

echo "✅ 测试代码已创建"

echo ""
echo "步骤 2: 编译汇编代码..."
nasm -f bin -o /tmp/dosbox_test/test.com /tmp/dosbox_test/test.asm
echo "✅ 编译成功"

echo ""
echo "步骤 3: 创建 DOSBox 配置..."
cat > /tmp/dosbox_test/test.conf << EOF
[cpu]
core=normal
cycles=max

[autoexec]
TRACE_ENABLE /tmp/dosbox_test/trace.json
MOUNT C: /tmp/dosbox_test
C:
test.com
TRACE_DISABLE
EXIT
EOF

echo "✅ 配置已创建"

echo ""
echo "步骤 4: 运行 DOSBox..."
$DOSBOX_PATH -conf /tmp/dosbox_test/test.conf -noconsole

echo ""
echo "步骤 5: 检查 trace 输出..."
if [ -f /tmp/dosbox_test/trace.json ]; then
    echo "✅ Trace 文件已生成"
    echo ""
    echo "Trace 内容:"
    echo "----------------------------------------"
    cat /tmp/dosbox_test/trace.json
    echo "----------------------------------------"
    echo ""

    # 验证 JSON 格式
    if command -v python3 &> /dev/null; then
        if python3 -c "import json; json.load(open('/tmp/dosbox_test/trace.json'))" 2>/dev/null; then
            echo "✅ JSON 格式正确"
        else
            echo "⚠️  JSON 格式可能有问题"
        fi
    fi

    echo ""
    echo "=========================================="
    echo "✅ 测试成功！"
    echo "=========================================="
else
    echo "❌ Trace 文件未生成"
    echo ""
    echo "可能的原因:"
    echo "  1. TRACE_ENABLE 命令未正确实现"
    echo "  2. TraceLogger 未正确编译"
    echo "  3. 文件路径权限问题"
    exit 1
fi

echo ""
echo "下一步:"
echo "  1. 测试 Code Executor: cd backend && python test_agent.py"
echo "  2. 启动后端: cd backend && python app_fastapi.py"
echo "  3. 使用 VS Code 插件测试端到端流程"
echo ""
