"""
Assembly Teaching Agent Core - LangChain Agent Framework
使用LangChain的create_agent实现ReAct架构
"""

from typing import Dict, Any, Optional, AsyncIterator
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .state_manager import AgentStateManager
from .langchain_tools import create_langchain_tools
from .prompts import SYSTEM_PROMPT
from .filtered_llm import FilteredChatOpenAI


class AssemblyTeachingAgentLangChain:
    """8086汇编教学Agent - 基于LangChain Agent Framework"""

    def __init__(self, api_key: str, model_name: str = "gpt-4", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.state_manager = AgentStateManager()

        # 创建LLM实例 - 使用自定义的 FilteredChatOpenAI 来过滤 reasoning_content
        llm_config = {
            "model": model_name,
            "api_key": api_key,
            "temperature": 0.7,
            "streaming": True,
            "store": False,  # 禁用存储功能
        }
        if base_url:
            llm_config["base_url"] = base_url

        self.llm = FilteredChatOpenAI(**llm_config)

    def _create_agent(self, session_id: int, mode: str):
        """创建LangChain Agent (返回CompiledStateGraph)"""
        # 创建工具
        tools = create_langchain_tools(
            api_key=self.api_key,
            model_name=self.model_name,
            base_url=self.base_url,
            state_manager=self.state_manager,
            session_id=session_id
        )

        # 获取会话状态信息
        state = self.state_manager.get_state(session_id)
        session_info = ""
        if state:
            session_info = f"""
- 模式: {state['mode']}
- 当前步骤: {state['current_step']}/{len(state['task_steps'])} 步
- Hint Level: {state['hint_level']}
- 需求: {state['requirement'][:100]}{'...' if len(state['requirement']) > 100 else ''}
"""

        # 创建system prompt
        mode_name = "需求引导模式 (Requirement Guide)" if mode == "requirement_guide" else "代码检查模式 (Code Check)"

        system_prompt = f"""你是一位经验丰富的8086汇编语言教学助手，采用苏格拉底式教学法。

# 核心教学原则

1. **永远不直接给出代码或答案**
   - 禁止提供任何汇编代码片段
   - 禁止直接指出错误位置或修改方案

2. **通过问题引导思考**
   - 每轮对话只问一个问题
   - 根据 hint_level 调整问题的明确程度

# 当前模式: {mode_name}

# 当前会话信息
{session_info}

# 工作流程（需求引导模式）

如果是需求引导模式，按以下流程操作：

1. **首先调用 get_state 获取当前状态**
   - 了解 task_steps（任务步骤）、current_step（当前步骤）、hint_level（提示等级）

2. **如果 task_steps 为空，调用 task_decomposer**
   - 传入 requirement（需求描述）
   - 拆解任务为具体步骤
   - 拆解完成后，直接告诉用户"现在请完成第一步的代码实现"（不要提问）

3. **如果学生提交了代码或回答了问题，调用 progress_evaluator 评估进度**
   - 可以传入 student_code（可选），或者不传（会自动从状态中获取）
   - 工具会自动从状态中获取 current_step、task_steps、requirement
   - 评估当前步骤是否完成

4. **根据进度评估结果决定下一步**
   - 如果当前步骤已完成：简短肯定（1句话），直接说"请继续完成下一步的代码"（不要提问）
   - 如果学生还没有开始写代码：直接说"请开始实现这一步的代码"（不要提问）
   - 如果学生已经提交了代码但有问题：调用 hint_generator 生成引导问题

5. **只在学生代码有问题时才使用 hint_generator**
   - 传入参数：
     * context: 包含学生代码、当前步骤描述、错误信息等的文本
     * hint_level: 从 get_state 获取
     * mode: "requirement_guide"
     * focus_area: 根据进度评估结果决定引导方向
   - 将问题作为最终答案返回

# 重要原则
- 刚拆解完任务 → 不要提问，直接让用户写代码
- 当前步骤完成 → 不要提问，直接让用户写下一步代码
- 学生回答了问题但还没写代码 → 不要继续提问，让用户写代码
- 只有学生代码有问题时 → 才通过问题引导
"""

        # 创建Agent使用create_agent (返回CompiledStateGraph)
        agent = create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=system_prompt
        )

        return agent

    async def process_message(
        self,
        session_id: int,
        user_message: str,
        mode: str,
        requirement: str = "",
        current_code: str = ""
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        处理用户消息（流式输出）

        Args:
            session_id: 会话ID
            user_message: 用户消息
            mode: 模式 ("requirement_guide" | "code_check")
            requirement: 需求描述

        Yields:
            响应数据块
        """
        try:
            # 获取或创建会话状态
            yield {
                "type": "status",
                "content": "🔄 初始化会话状态..."
            }

            state = self.state_manager.get_or_create_state(session_id, mode, requirement)

            yield {
                "type": "status",
                "content": f"📌 会话模式: {'需求引导' if mode == 'requirement_guide' else '代码检查'}"
            }

            # 检测用户是否主动放弃
            if self._detect_give_up(user_message):
                yield {
                    "type": "status",
                    "content": "💬 检测到求助信号，提升提示深度"
                }
                self.state_manager.increase_hint_level(session_id)
                state = self.state_manager.get_state(session_id)

            # 更新用户代码（优先使用消息中的代码块，其次使用当前编辑器代码）
            code = self._extract_code(user_message)
            if code:
                yield {
                    "type": "status",
                    "content": f"📝 检测到代码块 ({len(code)} 字符)"
                }
                self.state_manager.update_code(session_id, code)
                state['user_code'] = code
            elif current_code:
                # 如果消息中没有代码块，但有当前编辑器代码，则使用它
                yield {
                    "type": "status",
                    "content": f"📄 读取当前编辑器代码"
                }
                self.state_manager.update_code(session_id, current_code)
                state['user_code'] = current_code

            # 创建Agent
            yield {
                "type": "status",
                "content": "🤖 启动LangChain Agent..."
            }

            agent = self._create_agent(session_id, mode)

            # 构建输入
            agent_input = self._build_agent_input(state, user_message)

            yield {
                "type": "status",
                "content": "💭 Agent开始推理和工具调用..."
            }

            # 执行Agent（异步流式）
            full_response = ""
            try:
                # 使用astream来获取流式输出
                async for chunk in agent.astream(
                    {"messages": [HumanMessage(content=agent_input)]},
                    stream_mode="values"
                ):
                    # 获取最新的消息
                    if "messages" in chunk:
                        messages = chunk["messages"]
                        if messages:
                            last_message = messages[-1]
                            # 如果是AI消息，提取内容
                            if isinstance(last_message, AIMessage):
                                content = last_message.content
                                if content and content not in full_response:
                                    new_content = content[len(full_response):]
                                    full_response = content
                                    yield {
                                        "type": "content",
                                        "content": new_content
                                    }

            except Exception as e:
                # 如果流式执行失败，尝试非流式执行
                yield {
                    "type": "status",
                    "content": "⚠️ 流式执行失败，切换到标准模式..."
                }

                try:
                    result = await agent.ainvoke({"messages": [HumanMessage(content=agent_input)]})
                    output = ""
                    if "messages" in result:
                        messages = result["messages"]
                        if messages:
                            last_message = messages[-1]
                            if isinstance(last_message, AIMessage):
                                output = last_message.content

                                # 清理 reasoning_content
                                if hasattr(last_message, 'additional_kwargs'):
                                    if 'reasoning_content' in last_message.additional_kwargs:
                                        del last_message.additional_kwargs['reasoning_content']

                    # 逐字输出
                    for char in output:
                        full_response += char
                        yield {
                            "type": "content",
                            "content": char
                        }
                except Exception as inner_e:
                    yield {
                        "type": "error",
                        "content": f"Agent执行失败: {str(inner_e)}"
                    }
                    return

            # 如果没有生成任何内容，使用默认回复
            if not full_response.strip():
                full_response = "请告诉我更多关于你的想法，我会继续引导你。"
                yield {
                    "type": "content",
                    "content": full_response
                }

            yield {
                "type": "done",
                "content": ""
            }

        except Exception as e:
            yield {
                "type": "error",
                "content": f"Agent处理失败: {str(e)}"
            }

    def _build_agent_input(self, state: Dict[str, Any], user_message: str) -> str:
        """构建Agent输入"""
        input_parts = []

        input_parts.append(f"学生消息: {user_message}")

        if state['user_code']:
            input_parts.append(f"\n学生提交的代码:\n```asm\n{state['user_code']}\n```")

        return "\n".join(input_parts)

    def _extract_code(self, message: str) -> Optional[str]:
        """从消息中提取代码"""
        if "```" in message:
            parts = message.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # 奇数索引是代码块
                    code = part.strip()
                    if code.startswith("asm") or code.startswith("assembly"):
                        code = "\n".join(code.split("\n")[1:])
                    return code.strip()
        return None

    def _detect_give_up(self, message: str) -> bool:
        """检测用户是否主动放弃"""
        give_up_keywords = [
            "不知道", "不会", "告诉我", "直接给我",
            "答案是什么", "怎么写", "帮我写"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in give_up_keywords)


def create_assembly_agent_langchain(
    api_key: str,
    model_name: str = "gpt-4",
    base_url: Optional[str] = None
) -> AssemblyTeachingAgentLangChain:
    """
    创建基于LangChain的Assembly Teaching Agent实例

    Args:
        api_key: OpenAI API密钥
        model_name: 模型名称
        base_url: API基础URL

    Returns:
        AssemblyTeachingAgentLangChain实例
    """
    return AssemblyTeachingAgentLangChain(api_key, model_name, base_url)
