# AI Coding Tool - 8086 汇编教学助手

基于 VS Code 插件的 AI Agent 系统，采用苏格拉底式引导教学法，帮助学生学习 8086 16位汇编编程。

## 🎯 核心特性

- **苏格拉底式教学**: 通过提问引导，不直接给出答案
- **双模式支持**: Guide（引导编写）和 Debug（引导调试）
- **自动执行分析**: 集成 DOSBox，自动执行代码并分析 trace
- **动态提示强度**: 根据学生理解程度自动调整（0-3级）
- **完整 trace 记录**: 寄存器、标志位、内存、跳转信息

## 🚀 快速开始

### 1. 编译 DOSBox

```bash
./build_dosbox.sh
```

### 2. 测试 Trace 功能

```bash
./test_dosbox.sh
```

### 3. 启动后端

```bash
cd backend
python app_fastapi.py
```

### 4. 使用插件

1. 在 VS Code 中按 F5 启动调试
2. 打开 `.asm` 文件
3. 切换到 guided 模式
4. 开始对话

## 📚 文档

- **QUICKSTART_GUIDE.md** - 快速开始指南
- **INTEGRATION_COMPLETE.md** - 完整集成总结
- **DOSBOX_INTEGRATION.md** - DOSBox 集成详细指南
- **backend/AGENT_README.md** - Agent 系统架构
- **backend/QUICKSTART.md** - Agent 快速启动

## 🏗️ 系统架构

```
用户 (VS Code)
    ↓
MessageHandler (根据模式选择执行链)
    ↓
Backend API (FastAPI)
    ↓
Agent Core (LangChain ReAct)
    ↓
┌─────────────────────────────────┐
│  5 个工具:                       │
│  - Student Tree (学习进度)       │
│  - Code Analyzer (静态分析)      │
│  - Code Executor (执行+trace)    │
│  - Step Explainer (trace解析)    │
│  - Hint Generator (生成问题)     │
└─────────────────────────────────┘
    ↓
DOSBox (修改版，支持 trace)
    ↓
Trace Logger (记录执行状态)
    ↓
JSON 输出 → 数据库 → Agent 分析
    ↓
引导性问题 → 用户
```

## 📊 技术栈

- **前端**: VS Code Extension (TypeScript)
- **后端**: FastAPI (Python)
- **AI**: LangChain + OpenAI-compatible API
- **数据库**: SQLite
- **执行引擎**: DOSBox (修改版)
- **编译器**: NASM

## 🔧 系统要求

### macOS
```bash
brew install autoconf automake sdl sdl_net sdl_sound nasm
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get install build-essential autoconf automake \
    libsdl1.2-dev libsdl-net1.2-dev libsdl-sound1.2-dev nasm
```

## 📁 项目结构

```
.
├── backend/                    # 后端服务
│   ├── agent_core.py          # Agent 核心
│   ├── agent_tools/           # 5个工具模块
│   ├── agent_prompts/         # 4层提示词
│   ├── routers/               # API 路由
│   └── database.py            # 数据库
├── src/                       # VS Code 插件
│   └── providers/
│       └── MessageHandler.ts  # 消息处理（已集成 Agent）
├── dosbox-code-0-r4494-dosbox-trunk/  # DOSBox 源码
│   ├── include/
│   │   └── trace_logger.h     # Trace Logger 头文件
│   └── src/
│       ├── cpu/
│       │   ├── core_normal.cpp    # CPU 核心（已添加 hook）
│       │   └── trace_logger.cpp   # Trace Logger 实现
│       └── shell/
│           └── shell_cmds.cpp     # Shell 命令（已添加 TRACE）
├── build_dosbox.sh            # DOSBox 编译脚本
├── test_dosbox.sh             # Trace 功能测试脚本
└── *.md                       # 文档
```

## ✅ 已完成功能

### DOSBox 集成
- [x] Trace Logger 模块
- [x] CPU 核心 hook
- [x] Shell 命令（TRACE_ENABLE/TRACE_DISABLE）
- [x] JSON 格式输出

### Agent 系统
- [x] 5个工具模块
- [x] 4层提示词系统
- [x] ReAct 架构
- [x] 数据库表结构
- [x] 学习进度跟踪

### 前端集成
- [x] 自动检测汇编代码
- [x] 自动启用 Agent
- [x] 传递当前代码
- [x] 无需手动配置

### 测试和文档
- [x] 测试脚本
- [x] 编译脚本
- [x] 完整文档
- [x] 快速开始指南

## 🎓 使用示例

### 引导模式

**学生**: "我想写一个加法程序"

**Agent**: "很好！在开始之前，你能描述一下需要哪些步骤吗？"

**学生**: "先把数字放到寄存器里，然后相加"

**Agent**: "对的！那你觉得应该使用哪些寄存器呢？"

### 调试模式

**学生**: "我的代码结果不对"

**Agent**: "能说说你预期的结果是什么吗？"

**学生**: "我想让 AX = 8，但结果是 5"

**Agent**: "让我们一步步看。执行第一条指令后，AX 的值是多少？"

## 🔍 Trace 示例

```json
[
  {
    "step": 1,
    "instruction": "MOV AX, 5",
    "address": "0000:0100",
    "register_diff": {"AX": {"before": 0, "after": 5}},
    "flags_diff": {},
    "memory_write": null,
    "jump_info": null
  },
  {
    "step": 2,
    "instruction": "ADD AX, 3",
    "address": "0000:0103",
    "register_diff": {"AX": {"before": 5, "after": 8}},
    "flags_diff": {"ZF": {"before": 0, "after": 0}},
    "memory_write": null,
    "jump_info": null
  }
]
```

## 🐛 故障排除

查看 **QUICKSTART_GUIDE.md** 中的故障排除部分。

## 📈 下一步优化

- [ ] 添加指令反汇编
- [ ] 优化 trace 性能
- [ ] 添加 UI 可视化
- [ ] 支持更多汇编语法
- [ ] 添加更多教学场景

## 📝 许可证

本项目基于 DOSBox（GPL v2）开发。

## 🙏 致谢

- DOSBox Team
- LangChain
- OpenAI

---

**版本**: v1.0  
**状态**: Ready for Testing 🚀  
**日期**: 2026-04-09
