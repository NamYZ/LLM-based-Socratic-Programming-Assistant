# 后端代码调用关系分析

## 一、整体架构层次

```
┌─────────────────────────────────────┐
│           入口层 (Entry)             │
│         app_fastapi.py              │
├─────────────────────────────────────┤
│           路由层 (Routers)           │
│  config_router  session_router      │
│           chat_router               │
├─────────────────────────────────────┤
│           模型层 (Models)            │
│          models.py                  │
├─────────────────────────────────────┤
│          数据库层 (Database)          │
│         database.py                 │
├─────────────────────────────────────┤
│        Agent 核心层 (Core)           │
│        agent_core.py                │
├─────────────────────────────────────┤
│       Agent 工具层 (Tools)           │
│  student_tree   code_analyzer       │
│  code_executor  step_explainer      │
│      hint_generator                 │
├─────────────────────────────────────┤
│      Agent 提示词层 (Prompts)        │
│  system_prompt  mode_prompt         │
│  tool_prompt    task_prompt         │
├─────────────────────────────────────┤
│      Ask 提示词层 (Ask Prompts)      │
│  guided_mode   question_mode        │
└─────────────────────────────────────┘
```

---

## 二、各文件详细调用关系

### 1. 入口层

**app_fastapi.py**
- 导入 `config_router` (配置管理路由)
- 导入 `session_router` (会话管理路由)
- 导入 `chat_router` (聊天路由)
- 导入 `init_db`, `DB_PATH` 从 database.py
- 功能：创建 FastAPI 应用，注册 CORS 中间件，注册三个路由

---

### 2. 路由层

**config_router.py** (配置管理)
- 导入 `SettingsRequest`, `ConfigRequest` 从 models.py
- 导入 `DB_PATH`, `get_api_key`, `get_local_time` 从 database.py
- API 端点：
  - `GET /api/settings` - 获取当前配置
  - `POST /api/settings` - 保存配置
  - `GET /api/configs` - 获取所有配置列表
  - `GET /api/configs/{config_id}` - 获取单个配置详情
  - `POST /api/configs` - 添加新配置
  - `PUT /api/configs/{config_id}` - 更新配置
  - `DELETE /api/configs/{config_id}` - 删除配置
  - `POST /api/configs/{config_id}/activate` - 激活配置

**session_router.py** (会话管理)
- 导入 `DB_PATH`, `clear_session_history` 从 database.py
- API 端点：
  - `GET /api/sessions` - 获取会话列表
  - `DELETE /api/sessions/{sid}` - 删除会话
  - `GET /api/sessions/{sid}/messages` - 获取会话消息
  - `DELETE /api/history` - 清除所有历史

**chat_router.py** (聊天)
- 导入 `ChatRequest` 从 models.py
- 导入 `DB_PATH`, `get_api_key`, `get_local_time`, `auto_title`, `get_session_history` 从 database.py
- 导入 `GUIDED_SYSTEM_PROMPT`, `ANSWER_SYSTEM_PROMPT` 从 ask_prompts
- 导入 `create_agent` 从 agent_core.py
- API 端点：
  - `POST /api/chat` - 发送消息并获取 AI 回复

---

### 3. 模型层

**models.py**
- 定义 `SettingsRequest` (BaseModel) - 快速设置请求模型
- 定义 `ConfigRequest` (BaseModel) - 完整配置请求模型
- 定义 `ChatRequest` (BaseModel) - 聊天请求模型
- 被 config_router.py 和 chat_router.py 导入使用

---

### 4. 数据库层

**database.py**
- 定义 `SQLiteChatMessageHistory` 类 - 基于 SQLite 的聊天历史实现
- 定义 `session_histories` 字典 - 内存中的会话历史缓存
- 定义 `DB_PATH` - 数据库文件路径
- 函数：
  - `get_session_history(session_id)` - 获取或创建会话历史
  - `clear_session_history(session_id)` - 清除会话历史
  - `init_db()` - 初始化数据库表
  - `get_api_key()` - 获取当前激活的 API 配置
  - `get_local_time()` - 获取当前本地时间
  - `auto_title(msg)` - 自动生成会话标题
- 数据库表：
  - `model_configs_vscode` - 模型配置表
  - `sessions_vscode` - 会话表
  - `messages_vscode` - 消息表
  - `execution_traces` - 执行 trace 记录表
  - `student_progress` - 学生学习进度表
- 被多个路由和工具模块导入使用

---

### 5. Agent 核心层

**agent_core.py**
- 导入 `ChatOpenAI` 从 langchain_openai
- 导入 `create_langchain_agent`, `ToolCallLimitMiddleware` 从 langchain
- 导入工具函数：
  - `get_student_progress`, `update_student_progress` 从 agent_tools/student_tree.py
  - `analyze_code` 从 agent_tools/code_analyzer.py
  - `execute_code`, `get_execution_trace` 从 agent_tools/code_executor.py
  - `explain_step`, `explain_trace` 从 agent_tools/step_explainer.py
  - `generate_hint` 从 agent_tools/hint_generator.py
- 导入提示词：
  - `AGENT_SYSTEM_PROMPT` 从 agent_prompts/system_prompt.py
  - `get_mode_prompt` 从 agent_prompts/mode_prompt.py
  - `TOOL_DESCRIPTIONS` 从 agent_prompts/tool_prompt.py
  - `build_task_prompt` 从 agent_prompts/task_prompt.py
- 定义 `AssemblyTeachingAgent` 类：
  - `__init__(api_key, model_name, base_url)` - 初始化 Agent
  - `_create_tools()` - 创建工具列表
  - `_create_agent()` - 创建 LangChain Agent
  - `stream_process()` - 流式处理用户输入
  - `process()` - 处理用户输入返回回答
  - `detect_mode()` - 自动检测模式 (guide/debug)
- 定义 `create_agent()` 函数 - 创建 Agent 实例的工厂函数
- 被 chat_router.py 导入使用

---

### 6. Agent 工具层

**agent_tools/student_tree.py**
- 导入 `DB_PATH`, `get_local_time` 从 database.py
- 定义 `StudentTree` 类：
  - `get_progress(session_id)` - 获取学生学习进度
  - `update_progress(session_id, topic, question, answered, hint_level)` - 更新进度
  - `increase_hint_level(session_id, topic, question)` - 提高提示强度
  - `reset_progress(session_id)` - 重置进度
- 工具函数：
  - `get_student_progress(session_id)` - 供 Agent 调用
  - `update_student_progress(session_id, topic, question, answered, hint_level)` - 供 Agent 调用

**agent_tools/code_analyzer.py**
- 定义 `CodeAnalyzer` 类：
  - `analyze(code)` - 分析汇编代码
  - `_preprocess(code)` - 预处理代码
  - `_is_label(line)` - 判断是否是标签
  - `_parse_instruction(line)` - 解析指令
  - `_extract_register(operand)` - 提取寄存器
  - `_check_operand_mismatch()` - 检查操作数不匹配
  - `_check_segment_usage()` - 检查段寄存器使用
  - `_check_division()` - 检查除法指令
- 工具函数：
  - `analyze_code(code)` - 供 Agent 调用

**agent_tools/code_executor.py**
- 导入 `DB_PATH`, `get_local_time` 从 database.py
- 定义 `CodeExecutor` 类：
  - `__init__(dosbox_path)` - 初始化执行器
  - `_find_dosbox()` - 查找 DOSBox 可执行文件
  - `execute(code, session_id)` - 执行汇编代码
  - `_prepare_com_program(code)` - 准备 COM 程序
  - `_execute_with_dosbox(asm_file, trace_file)` - 使用 DOSBox 执行
  - `_get_mock_trace()` - 获取模拟 trace 数据
  - `_save_trace_to_db(execution_id, session_id, trace_data)` - 保存 trace 到数据库
  - `get_trace(execution_id)` - 获取执行的 trace 数据
- 工具函数：
  - `execute_code(code, session_id)` - 供 Agent 调用
  - `get_execution_trace(execution_id)` - 供 Agent 调用

**agent_tools/step_explainer.py**
- 定义 `StepExplainer` 类：
  - `explain_step(step_data)` - 解释单步执行
  - `explain_trace(trace_data)` - 解释完整 trace
  - `get_key_changes(trace_data)` - 提取关键变化
- 工具函数：
  - `explain_step(step_data)` - 供 Agent 调用
  - `explain_trace(trace_data)` - 供 Agent 调用

**agent_tools/hint_generator.py**
- 定义 `HintGenerator` 类：
  - `generate(context, hint_level)` - 生成引导性问题
  - `_generate_guide_hint(context, hint_level)` - 生成引导模式问题
  - `_generate_debug_hint(context, hint_level)` - 生成调试模式问题
- 工具函数：
  - `generate_hint(context, hint_level)` - 供 Agent 调用

---

### 7. Agent 提示词层

**agent_prompts/system_prompt.py**
- 定义 `AGENT_SYSTEM_PROMPT` - Agent 系统提示词
- 被 agent_core.py 导入使用

**agent_prompts/mode_prompt.py**
- 定义 `GUIDE_MODE_PROMPT` - 引导模式提示词
- 定义 `DEBUG_MODE_PROMPT` - 调试模式提示词
- 定义 `get_mode_prompt(mode)` 函数 - 根据模式返回对应提示词
- 被 agent_core.py 导入使用

**agent_prompts/tool_prompt.py**
- 定义 `TOOL_DESCRIPTIONS` - 工具描述文本
- 被 agent_core.py 导入使用

**agent_prompts/task_prompt.py**
- 定义 `build_task_prompt(user_message, current_code, student_progress, trace_analysis, mode)` 函数 - 构建任务提示词
- 被 agent_core.py 导入使用

---

### 8. Ask 提示词层

**ask_prompts/guided_mode_prompts.py**
- 定义 `GUIDED_SYSTEM_PROMPT` - 引导式系统提示词（苏格拉底式教学法）
- 被 chat_router.py 导入使用

**ask_prompts/question_mode_prompts.py**
- 定义 `ANSWER_SYSTEM_PROMPT` - 答案式系统提示词（直接代码输出）
- 被 chat_router.py 导入使用

---

## 三、核心调用链

### 1. 普通聊天模式调用链：
```
app_fastapi.py 
  → chat_router.py 
    → models.py (ChatRequest)
    → database.py (get_api_key, get_session_history)
    → ask_prompts/ (GUIDED_SYSTEM_PROMPT / ANSWER_SYSTEM_PROMPT)
    → LangChain ChatOpenAI
```

### 2. Agent 模式调用链：
```
app_fastapi.py 
  → chat_router.py 
    → agent_core.py 
      → agent_tools/student_tree.py (get_student_progress)
      → agent_tools/code_analyzer.py (analyze_code)
      → agent_tools/code_executor.py (execute_code, get_execution_trace)
      → agent_tools/step_explainer.py (explain_step, explain_trace)
      → agent_tools/hint_generator.py (generate_hint)
      → agent_prompts/ (各种提示词)
      → LangChain Agent
```

### 3. 配置管理调用链：
```
app_fastapi.py 
  → config_router.py 
    → models.py (SettingsRequest, ConfigRequest)
    → database.py (DB_PATH, get_api_key, get_local_time)
```

### 4. 会话管理调用链：
```
app_fastapi.py 
  → session_router.py 
    → database.py (DB_PATH, clear_session_history)
```

---

## 四、依赖关系总结

| 文件 | 被谁导入 | 导入谁 |
|------|----------|--------|
| app_fastapi.py | - | routers/*, database |
| config_router.py | app_fastapi | models, database |
| session_router.py | app_fastapi | database |
| chat_router.py | app_fastapi | models, database, ask_prompts, agent_core |
| models.py | config_router, chat_router | - |
| database.py | app_fastapi, routers, agent_tools/* | - |
| agent_core.py | chat_router | agent_tools/*, agent_prompts/* |
| agent_tools/* | agent_core | database |
| agent_prompts/* | agent_core | - |
| ask_prompts/* | chat_router | - |
