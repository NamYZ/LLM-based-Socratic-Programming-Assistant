"""
聊天路由
处理聊天消息的发送和 AI 回复的流式返回
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import sqlite3
import json
import re
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from models import ChatRequest
from database import DB_PATH, get_api_key, get_local_time, auto_title, get_session_history
from guided_mode_prompts import GUIDED_SYSTEM_PROMPT
from question_mode_prompts import ANSWER_SYSTEM_PROMPT
from agent_core import create_agent

router = APIRouter()


def contains_code(text: str) -> bool:
    """
    检查文本中是否包含代码相关内容
    返回 True 表示包含代码，False 表示不包含
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


def resolve_agent_mode(request_mode: str, detected_mode: str) -> str:
    """
    将前端会话模式映射为 Agent 内部子模式。
    - agent: 由 Agent 自动检测 guide/debug
    - guided: 固定走 guide
    - debug/guide: 透传给 Agent
    - 其他模式: 回退到自动检测结果
    """
    if request_mode == 'guided':
        return 'guide'
    if request_mode in ('guide', 'debug'):
        return request_mode
    return detected_mode


def build_agent_step(phase: str, title: str, content: str = "", status: str = "info") -> dict:
    """统一 Agent 过程事件结构。"""
    return {
        "phase": phase,
        "title": title,
        "content": content,
        "status": status
    }


@router.post("/api/chat")
async def chat(req: ChatRequest):
    """聊天接口：接收用户发的消息 → 存到数据库 → 调用 AI → 逐字返回回答 → 再把 AI 回答存进数据库"""
    if not req.message:
        raise HTTPException(status_code=400, detail='消息不能为空')

    # 获取AI配置
    api_key, model_name, provider, base_url = get_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail='请先配置 API Key')

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

    # Agent 模式的生成函数
    def generate_with_agent():
        try:
            # 创建 Agent
            agent = create_agent(api_key, model_name, base_url)

            # 自动检测模式（如果前端没有明确指定）
            detected_mode = agent.detect_mode(req.message, req.current_code or "")
            agent_mode = resolve_agent_mode(req.mode, detected_mode)
            final_answer = ""

            # 发送思考状态
            yield f"data: {json.dumps({'status': 'thinking'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'agent_step': build_agent_step('mode', f'已进入 {agent_mode} 模式', 'Agent 正在分析问题并规划后续工具调用。')}, ensure_ascii=False)}\n\n"

            # 流式接收 Agent 过程
            for event in agent.stream_process(
                user_message=req.message,
                current_code=req.current_code or "",
                session_id=session_id,
                mode=agent_mode
            ):
                if event.get('kind') == 'agent_step':
                    yield f"data: {json.dumps({'agent_step': event}, ensure_ascii=False)}\n\n"
                elif event.get('kind') == 'final_answer':
                    final_answer = event.get('content', '')

            if not final_answer:
                final_answer = "抱歉，我无法生成合适的引导问题。"

            # 发送生成状态
            yield f"data: {json.dumps({'status': 'generating'}, ensure_ascii=False)}\n\n"

            # 逐字输出结果
            for char in final_answer:
                yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"

            # 保存到数据库
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO messages_vscode (session_id, role, content, created_at) VALUES (?,?,?,?)",
                      (session_id, 'assistant', final_answer, get_local_time()))
            c.execute("UPDATE sessions_vscode SET updated_at=? WHERE id=?", (get_local_time(), session_id))
            conn.commit()
            conn.close()

            # 完成
            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'is_new_session': is_new}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = f"Agent 处理失败: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"

    # AI 模型流式输出回答，边生成边返回给前端，同时把完整回答存到数据库里
    def generate():
        try:
            # 如果启用 Agent 模式
            if req.use_agent or req.mode == 'agent':
                yield from generate_with_agent()
                return

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
