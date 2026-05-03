"""
聊天路由：处理聊天消息发送 - AI 回复的 API 请求
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import sqlite3
import json
import re
import sys
import os
import importlib
import traceback

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT in sys.path:
    sys.path.remove(BACKEND_ROOT)
sys.path.insert(0, BACKEND_ROOT)

# 导入 langchain 相关模块
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

# 导入自定义模块
from models import ChatRequest
from database import DB_PATH, get_api_key, get_local_time, auto_title, get_session_history
from ask_prompts import GUIDED_SYSTEM_PROMPT, ANSWER_SYSTEM_PROMPT

_ASSEMBLY_AGENT_IMPORT_ERROR = None


def get_assembly_agent_class():
    """优先加载当前项目 backend 目录下的 AssemblyTeachingAgent。"""
    global _ASSEMBLY_AGENT_IMPORT_ERROR

    package_dir = os.path.join(BACKEND_ROOT, 'assembly_agent')

    try:
        cached_module = sys.modules.get('assembly_agent')
        cached_module_path = getattr(cached_module, '__file__', '') if cached_module else ''
        local_package_prefix = os.path.abspath(package_dir) + os.sep

        # 避免被环境里同名的第三方模块覆盖。
        if cached_module and (
            not cached_module_path or
            not os.path.abspath(cached_module_path).startswith(local_package_prefix)
        ):
            sys.modules.pop('assembly_agent', None)

        module = importlib.import_module('assembly_agent')
        agent_class = getattr(module, 'AssemblyTeachingAgent', None)
        if agent_class is None:
            raise ImportError('assembly_agent 模块中未导出 AssemblyTeachingAgent')

        _ASSEMBLY_AGENT_IMPORT_ERROR = None
        return agent_class
    except Exception as exc:
        _ASSEMBLY_AGENT_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        print(f"[WARNING] Failed to load Assembly Teaching Agent: {_ASSEMBLY_AGENT_IMPORT_ERROR}")
        traceback.print_exc()
        return None


router = APIRouter()


def contains_code(text: str) -> bool:
    """
    检查文本中是否包含代码相关内容：返回 True 表示包含代码, False 表示不包含
    """
    # 检查代码块标记
    if '```' in text or '`' in text:
        return True

    # 检查常见编程符号（连续出现）
    code_symbols = [
        r'\{[^}]*\}',  # 花括号
        r'\[[^\]]*\]',  # 方括号（但要排除中文标点）
        r'\([^)]*\)',  # 圆括号（但要排除普通文本）
        r'[a-zA-Z_][a-zA-Z0-9_]*\s*\(',  # 函数调用模式
        r'[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*',  # 赋值语句
        r'->\s*',  # 箭头函数
        r'=>\s*',  # 箭头函数
        r'::\s*',  # 作用域解析
        r'\.\s*[a-zA-Z_]',  # 点号访问
        r'[;{}]\s*$',  # 语句结束符
    ]

    for pattern in code_symbols:
        if re.search(pattern, text):
            return True

    # 检查常见编程关键字（需要是独立单词）
    code_keywords = [
        r'\bfunction\b', r'\bdef\b', r'\bclass\b', r'\bimport\b', r'\bfrom\b',
        r'\breturn\b', r'\bif\b', r'\belse\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
        r'\btry\b', r'\bcatch\b', r'\bexcept\b', r'\bfinally\b', r'\bawait\b',
        r'\basync\b', r'\bconst\b', r'\blet\b', r'\bvar\b', r'\bpublic\b',
        r'\bprivate\b', r'\bprotected\b', r'\bstatic\b', r'\bvoid\b',
        r'\bint\b', r'\bfloat\b', r'\bstring\b', r'\bbool\b', r'\barray\b',
        r'\bnull\b', r'\bundefined\b', r'\btrue\b', r'\bfalse\b',
        r'\bconsole\.log\b', r'\bprint\b', r'\bprintln\b',
    ]

    for keyword in code_keywords:
        if re.search(keyword, text, re.IGNORECASE):
            return True

    # 检查多行缩进模式（可能是代码）
    lines = text.split('\n')
    indented_lines = [line for line in lines if line.startswith('    ') or line.startswith('\t')]
    if len(indented_lines) >= 2:
        return True

    return False


async def handle_assembly_agent(req: ChatRequest, api_key: str, model_name: str, base_url: str, agent_class):
    """处理Assembly Teaching Agent模式的请求"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 创建或获取会话
    is_new = False
    session_id = req.session_id
    if not session_id:
        title = auto_title(req.message)
        local_time = get_local_time()
        c.execute("INSERT INTO sessions_vscode (title, mode, created_at, updated_at) VALUES (?,?,?,?)",
                  (title, req.mode, local_time, local_time))
        session_id = c.lastrowid
        conn.commit()
        is_new = True

    # 存储用户消息
    c.execute("INSERT INTO messages_vscode (session_id, role, content, created_at) VALUES (?,?,?,?)",
              (session_id, 'user', req.message, get_local_time()))
    conn.commit()
    conn.close()

    # 创建Agent实例
    agent = agent_class(api_key, model_name, base_url)

    # 确定Agent模式
    agent_mode = "requirement_guide" if req.mode == "assembly_guide" else "code_check"

    # 提取需求（从消息或代码上下文）
    requirement = req.message
    if hasattr(req, 'codeContexts') and req.codeContexts:
        # 如果有代码上下文，将其作为需求的一部分
        context_text = "\n\n".join([f"文件: {ctx.get('fileName', '')}\n```\n{ctx.get('content', '')}\n```"
                                     for ctx in req.codeContexts])
        requirement = f"{req.message}\n\n相关代码:\n{context_text}"

    # 提取当前编辑器中的代码
    current_code = req.current_code if req.current_code else ""

    async def generate():
        try:
            full_reply = ""

            # 调用Agent处理消息
            async for chunk in agent.process_message(
                session_id=session_id,
                user_message=req.message,
                mode=agent_mode,
                requirement=requirement,
                current_code=current_code  # 传递当前代码
            ):
                chunk_type = chunk.get('type')
                content = chunk.get('content', '')

                if chunk_type == 'status':
                    # 发送状态更新
                    yield f"data: {json.dumps({'status': content}, ensure_ascii=False)}\n\n"

                elif chunk_type == 'task_steps':
                    # 发送任务步骤
                    yield f"data: {json.dumps({'task_steps': content}, ensure_ascii=False)}\n\n"

                elif chunk_type == 'content':
                    # 发送内容
                    full_reply += content
                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

                elif chunk_type == 'done':
                    # 完成
                    break

                elif chunk_type == 'error':
                    # 错误
                    yield f"data: {json.dumps({'error': content}, ensure_ascii=False)}\n\n"
                    return

            # 保存AI回复到数据库
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO messages_vscode (session_id, role, content, created_at) VALUES (?,?,?,?)",
                      (session_id, 'assistant', full_reply, get_local_time()))
            c.execute("UPDATE sessions_vscode SET updated_at=? WHERE id=?", (get_local_time(), session_id))
            conn.commit()
            conn.close()

            # 获取任务完成状态
            from assembly_agent.state_manager import AgentStateManager
            state_manager = AgentStateManager()
            state = state_manager.get_state(session_id)
            completion_status = state.get('completion_status', 'in_progress') if state else 'in_progress'

            # 发送完成信号（包含completion_status）
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'is_new_session': is_new, 'completion_status': completion_status}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = f"Assembly Agent错误: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@router.post("/api/chat")
async def chat(req: ChatRequest):
    """聊天接口：接收用户发的消息 → 存到数据库 → 调用 AI → 逐字返回回答 → 再把 AI 回答存进数据库"""
    if not req.message:
        raise HTTPException(status_code=400, detail='消息不能为空')

    # 获取AI配置
    api_key, model_name, provider, base_url = get_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail='请先配置 API Key')

    # 检查是否使用Assembly Teaching Agent模式
    if req.mode in ['assembly_guide', 'assembly_check']:
        assembly_agent_class = get_assembly_agent_class()
        if assembly_agent_class is None:
            detail = 'Assembly Teaching Agent加载失败'
            if _ASSEMBLY_AGENT_IMPORT_ERROR:
                detail = f'{detail}: {_ASSEMBLY_AGENT_IMPORT_ERROR}'
            raise HTTPException(status_code=500, detail=detail)
        return await handle_assembly_agent(req, api_key, model_name, base_url, assembly_agent_class)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 如果前端没有传 session_id，说明这是一个新对话，需要先在 sessions_vscode 表里创建一个新会话记录
    is_new = False
    session_id = req.session_id
    if not session_id:
        title = auto_title(req.message)
        local_time = get_local_time()
        c.execute("INSERT INTO sessions_vscode (title, mode, created_at, updated_at) VALUES (?,?,?,?)",
                  (title, req.mode, local_time, local_time))
        session_id = c.lastrowid
        conn.commit()
        is_new = True

    # 然后把用户的消息存到 messages_vscode 表里，关联到这个 session_id
    c.execute("INSERT INTO messages_vscode (session_id, role, content, created_at) VALUES (?,?,?,?)",
              (session_id, 'user', req.message, get_local_time()))

    conn.commit()
    conn.close()

    # AI 模型流式输出回答，边生成边返回给前端，同时把完整回答存到数据库里
    def generate():
        try:
            # 准备模型参数，使用前端传来的采样参数或默认值
            model_kwargs = {
                'model': model_name,
                'openai_api_key': api_key,
                'openai_api_base': base_url,
                'streaming': True,  # 逐字返回
            }

            # 如果前端传来了采样参数，则使用它们
            if req.samplingParams:
                print(f"[DEBUG] 收到采样参数: {req.samplingParams}")
                if 'temperature' in req.samplingParams:
                    model_kwargs['temperature'] = req.samplingParams['temperature']
                if 'top_p' in req.samplingParams:
                    model_kwargs['top_p'] = req.samplingParams['top_p']
                if 'frequency_penalty' in req.samplingParams:
                    model_kwargs['frequency_penalty'] = req.samplingParams['frequency_penalty']
                if 'presence_penalty' in req.samplingParams:
                    model_kwargs['presence_penalty'] = req.samplingParams['presence_penalty']
                print(f"[DEBUG] 应用后的 model_kwargs: {model_kwargs}")
            else:
                # 默认值
                model_kwargs['temperature'] = 0.7
                print(f"[DEBUG] 未收到采样参数，使用默认值")

            model = ChatOpenAI(**model_kwargs)

            # 构建带有历史记录的 Runnable Chain
            if req.mode == 'guided':
                prompt = ChatPromptTemplate.from_messages([
                    ('system', GUIDED_SYSTEM_PROMPT),
                    MessagesPlaceholder(variable_name='history'),
                    ('human', '{input}')
                ])
            else:
                # 答案式模式使用 ANSWER_SYSTEM_PROMPT
                prompt = ChatPromptTemplate.from_messages([
                    ('system', ANSWER_SYSTEM_PROMPT),
                    MessagesPlaceholder(variable_name='history'),
                    ('human', '{input}')
                ])

            # 创建基础 chain
            chain = prompt | model

            # 使用 RunnableWithMessageHistory 包装 chain
            chain_with_history = RunnableWithMessageHistory(
                chain,
                get_session_history,
                input_messages_key="input",
                history_messages_key="history",
            )

            # 引导式模式下的代码检查和重新生成机制
            max_retries = 2
            retry_count = 0
            full_reply = ""

            while retry_count <= max_retries:
                full_reply = ""

                # 使用 RunnableWithMessageHistory 进行流式调用
                config = {"configurable": {"session_id": session_id}}

                # 发送思考状态
                yield f"data: {json.dumps({'status': 'thinking'}, ensure_ascii=False)}\n\n"

                # 逐字接收 AI 返回的回答，并实时流式输出给前端
                first_chunk = True
                for chunk in chain_with_history.stream(
                    {"input": req.message},
                    config=config
                ):
                    if chunk.content:
                        # 第一个内容块时，发送生成状态
                        if first_chunk:
                            yield f"data: {json.dumps({'status': 'generating'}, ensure_ascii=False)}\n\n"
                            first_chunk = False

                        full_reply += chunk.content
                        # 实时流式输出给前端
                        yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"

                # 引导式模式下检查是否包含代码
                if req.mode == 'guided':
                    if contains_code(full_reply):
                        retry_count += 1
                        if retry_count <= max_retries:
                            # 需要重新生成，先清除刚才添加的消息
                            history = get_session_history(session_id)
                            if len(history.messages) >= 2:
                                # 移除最后两条消息（用户输入和AI回复）
                                history.messages.pop()
                                history.messages.pop()

                            # 添加额外的系统提示
                            history.add_message(HumanMessage(content=req.message))
                            history.add_message(AIMessage(content=full_reply))
                            history.add_message(SystemMessage(content="你的回答中包含了代码内容，这违反了引导式教学的原则。请重新组织语言，完全不要出现任何代码、代码符号或代码关键字，只用自然语言描述思路和概念。"))

                            # 重新调用
                            full_reply = ""
                            # 发送重新思考状态
                            yield f"data: {json.dumps({'status': 'thinking'}, ensure_ascii=False)}\n\n"

                            first_chunk = True
                            for chunk in chain_with_history.stream(
                                {"input": "请用纯自然语言重新回答"},
                                config=config
                            ):
                                if chunk.content:
                                    if first_chunk:
                                        yield f"data: {json.dumps({'status': 'generating'}, ensure_ascii=False)}\n\n"
                                        first_chunk = False
                                    full_reply += chunk.content
                                    yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
                            continue
                        else:
                            # 超过最大重试次数，返回固定回复
                            full_reply = "抱歉，我无法提供代码相关内容，只能为你讲解思路。"
                            # 输出固定回复
                            for char in full_reply:
                                yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                            break
                    else:
                        # 不包含代码，直接使用
                        break
                else:
                    # 答案式模式，不需要检查
                    break

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # 把 AI 的完整回答存到数据库里，关联到同一个 session_id
            c.execute("INSERT INTO messages_vscode (session_id, role, content, created_at) VALUES (?,?,?,?)",
                      (session_id, 'assistant', full_reply, get_local_time()))
            c.execute("UPDATE sessions_vscode SET updated_at=? WHERE id=?", (get_local_time(), session_id))
            conn.commit()
            conn.close()

            # 告诉前端回答已经完成，返回 session_id 和是否是新会话的标志
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'is_new_session': is_new}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = str(e)
            # 根据错误类型提供更详细的提示
            if 'API key' in error_msg or 'api_key' in error_msg or 'Unauthorized' in error_msg or '401' in error_msg:
                detailed_error = '❌ API Key 配置错误或已失效，请检查配置文件中的 API Key 是否正确'
            elif 'Connection' in error_msg or 'timeout' in error_msg or 'Network' in error_msg:
                detailed_error = '❌ 网络连接失败，请检查网络连接或 Base URL 配置是否正确'
            elif 'model' in error_msg.lower() or 'not found' in error_msg.lower():
                detailed_error = '❌ 模型配置错误，请检查模型名称是否正确'
            else:
                detailed_error = f'❌ 请求失败: {error_msg}\n\n💡 请检查：\n1. API Key 是否正确\n2. Base URL 是否正确\n3. 网络连接是否正常\n4. 模型名称是否正确'

            yield f"data: {json.dumps({'error': detailed_error}, ensure_ascii=False)}\n\n"

    # 告诉 FastAPI：这是流式输出，不要缓存，实时推送
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )
