#!/bin/bash
# 查找 DOSBox 源代码中所有 AI 教学相关的修改

echo "=========================================="
echo "DOSBox AI 教学修改查找工具"
echo "=========================================="
echo ""

DOSBOX_DIR="./dosbox-code-0-r4494-dosbox-trunk"

if [ ! -d "$DOSBOX_DIR" ]; then
    echo "❌ DOSBox 目录不存在: $DOSBOX_DIR"
    exit 1
fi

echo "搜索所有带有 'AI TEACHING MODIFICATION' 标记的文件..."
echo ""

# 查找所有包含修改标记的文件
FILES=$(grep -r "AI TEACHING MODIFICATION" "$DOSBOX_DIR" --include="*.cpp" --include="*.h" -l)

if [ -z "$FILES" ]; then
    echo "❌ 未找到任何修改标记"
    exit 1
fi

echo "找到以下修改的文件:"
echo "=========================================="

for file in $FILES; do
    # 获取相对路径
    rel_path=${file#$DOSBOX_DIR/}

    # 统计修改块数量
    mod_count=$(grep -c "AI TEACHING MODIFICATION START" "$file")

    echo ""
    echo "📄 文件: $rel_path"
    echo "   修改块数: $mod_count"
    echo "   修改位置:"

    # 显示每个修改块的行号和简短描述
    grep -n "AI TEACHING MODIFICATION" "$file" | while read line; do
        line_num=$(echo "$line" | cut -d: -f1)
        content=$(echo "$line" | cut -d: -f2-)

        if [[ "$content" == *"START"* ]]; then
            # 读取下一行的注释作为描述
            desc=$(sed -n "$((line_num + 1))p" "$file" | sed 's/^[[:space:]]*\/\/ //')
            echo "   - 行 $line_num: $desc"
        fi
    done
done

echo ""
echo "=========================================="
echo "✅ 搜索完成"
echo ""
echo "详细信息请查看: DOSBOX_MODIFICATIONS.md"
echo "=========================================="
