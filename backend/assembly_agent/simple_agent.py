"""
简化的 Agent 实现 - 不使用 LangChain 的 create_agent
手动实现工具调用循环，完全控制消息处理
"""

from typing import Dict, Any, Optional, AsyncIterator
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import re

from .state_manager import AgentStateManager
from .langchain_tools import create_langchain_tools
from .filtered_llm import FilteredChatOpenAI
from .prompts.system_prompt import SYSTEM_PROMPT
from .prompts.mode_prompts import REQUIREMENT_GUIDE_PROMPT, CODE_CHECK_PROMPT


class SimpleReActAgent:
    """简化的 ReAct Agent - 手动实现工具调用"""

    def __init__(self, llm, tools, system_prompt: str):
        self.llm = llm
        self.tools = {tool.name: tool for tool in tools}
        self.system_prompt = system_prompt

    async def run(self, user_input: str, max_iterations: int = 5) -> AsyncIterator[Dict[str, Any]]:
        """运行 Agent"""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_input)
        ]

        for iteration in range(max_iterations):
            # 调用 LLM
            try:
                yield {
                    "type": "status",
                    "content": f"💭 Agent 正在思考... (第 {iteration + 1}/{max_iterations} 轮)"
                }

                response = await self.llm.ainvoke(messages)

                # 清理 reasoning_content
                if hasattr(response, 'additional_kwargs') and 'reasoning_content' in response.additional_kwargs:
                    del response.additional_kwargs['reasoning_content']

                content = response.content

                # 检查是否需要调用工具
                tool_call = self._parse_tool_call(content)

                if tool_call:
                    tool_name = tool_call['name']
                    tool_input = tool_call['input']

                    yield {
                        "type": "status",
                        "content": f"🛠️ 调用工具: {tool_name}"
                    }

                    # 显示工具参数（如果有）
                    if tool_input:
                        params_str = ", ".join([f"{k}={v[:30]}..." if isinstance(v, str) and len(v) > 30 else f"{k}={v}" for k, v in tool_input.items()])
                        yield {
                            "type": "status",
                            "content": f"📋 工具参数: {params_str}"
                        }

                    # 调用工具
                    if tool_name in self.tools:
                        try:
                            tool = self.tools[tool_name]

                            yield {
                                "type": "status",
                                "content": f"⚙️ 执行工具 {tool_name}..."
                            }

                            tool_result = tool.invoke(tool_input)

                            # 显示工具结果摘要
                            result_preview = tool_result[:80] + "..." if len(tool_result) > 80 else tool_result
                            yield {
                                "type": "status",
                                "content": f"✅ 工具 {tool_name} 执行完成: {result_preview}"
                            }

                            # 添加工具结果到消息历史
                            messages.append(AIMessage(content=content))
                            messages.append(HumanMessage(content=f"工具 {tool_name} 的结果:\n{tool_result}"))

                            # 继续下一轮
                            continue
                        except Exception as e:
                            # 友好的错误提示
                            error_msg = self._format_tool_error(tool_name, str(e))
                            yield {
                                "type": "status",
                                "content": error_msg
                            }
                            # 将错误信息添加到消息历史，让 Agent 知道出错了
                            messages.append(AIMessage(content=content))
                            messages.append(HumanMessage(content=f"工具调用出错: {error_msg}\n请调整参数后重试。"))
                            continue  # 继续而不是中断，让 Agent 有机会重试
                    else:
                        yield {
                            "type": "status",
                            "content": f"⚠️ 未知工具: {tool_name}"
                        }
                        break
                else:
                    # 没有工具调用，返回最终答案
                    yield {
                        "type": "content",
                        "content": content
                    }
                    break

            except Exception as e:
                yield {
                    "type": "error",
                    "content": f"LLM 调用失败: {str(e)}"
                }
                break

    def _parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """解析工具调用"""
        # 尝试解析文本格式的工具调用
        # 格式: Action: tool_name\nAction Input: {...}
        action_match = re.search(r'Action:\s*(\w+)', content)
        input_match = re.search(r'Action Input:\s*(\{.*?\})', content, re.DOTALL)

        if action_match:
            tool_name = action_match.group(1)
            tool_input = {}
            if input_match:
                try:
                    tool_input = json.loads(input_match.group(1))
                except Exception as e:
                    # JSON 解析失败，尝试提取关键信息
                    print(f"[DEBUG] JSON 解析失败: {e}, 原始输入: {input_match.group(1)}")
                    pass
            return {
                "name": tool_name,
                "input": tool_input
            }

        return None

    def _format_tool_error(self, tool_name: str, error_msg: str) -> str:
        """将技术性错误转换为友好的提示"""
        # 解析 Pydantic 验证错误
        if "validation error" in error_msg.lower():
            # 提取缺失的字段名
            missing_fields = re.findall(r'(\w+)\s+Field required', error_msg)

            if missing_fields:
                fields_str = "、".join(missing_fields)
                return f"⚠️ 系统内部错误：工具 {tool_name} 缺少必要参数 ({fields_str})，正在自动修复..."
            else:
                return f"⚠️ 系统内部错误：工具 {tool_name} 参数格式不正确，正在自动修复..."

        # 其他错误
        return f"⚠️ 系统内部错误：{error_msg}"


class AssemblyTeachingAgentSimple:
    """8086汇编教学Agent - 简化实现"""

    def __init__(self, api_key: str, model_name: str = "gpt-4", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.state_manager = AgentStateManager()

        # 创建LLM实例
        llm_config = {
            "model": model_name,
            "api_key": api_key,
            "temperature": 0.7,
            "streaming": False,  # 简化版不使用流式
            "store": False,
        }
        if base_url:
            llm_config["base_url"] = base_url

        self.llm = FilteredChatOpenAI(**llm_config)

    async def process_message(
        self,
        session_id: int,
        user_message: str,
        mode: str,
        requirement: str = "",
        current_code: str = ""
    ) -> AsyncIterator[Dict[str, Any]]:
        """处理用户消息"""
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

            # 检测用户是否主动放弃（自动增加提示等级）
            if self._detect_give_up(user_message):
                yield {
                    "type": "status",
                    "content": "💡 检测到困惑，提升引导明确度..."
                }
                self.state_manager.increase_hint_level(session_id)
                state = self.state_manager.get_state(session_id)

            # 检测用户是否已经理解了问题
            user_understood = self._detect_understanding(user_message)

            # 检测用户是否在确认代码正确性
            user_asking_confirmation = self._detect_confirmation(user_message)

            # 更新用户代码（优先使用消息中的代码块，其次使用当前编辑器代码）
            code = self._extract_code(user_message)
            if code:
                yield {
                    "type": "status",
                    "content": f"📝 检测到代码块"
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

            # 创建工具
            tools = create_langchain_tools(
                api_key=self.api_key,
                model_name=self.model_name,
                base_url=self.base_url,
                state_manager=self.state_manager,
                session_id=session_id
            )

            # 根据模式过滤工具
            if mode == "code_check":
                # 代码检查模式：只允许使用 code_validator, hint_generator, get_state
                allowed_tools = ["code_validator", "hint_generator", "get_state"]
                tools = [tool for tool in tools if tool.name in allowed_tools]
            elif mode == "requirement_guide":
                # 需求引导模式：允许使用所有工具
                pass

            # 构建系统提示
            # 使用基础 system prompt
            base_system_prompt = SYSTEM_PROMPT

            # 根据模式添加特定的 prompt
            if mode == "requirement_guide":
                mode_prompt = REQUIREMENT_GUIDE_PROMPT.format(
                    task_steps="\n".join([f"{i+1}. {step}" for i, step in enumerate(state['task_steps'])]) if state['task_steps'] else "（尚未拆解任务）",
                    current_step=state['current_step'],
                    total_steps=len(state['task_steps']),
                    current_step_description=state['task_steps'][state['current_step']-1] if state['task_steps'] and 0 < state['current_step'] <= len(state['task_steps']) else "（等待任务拆解）",
                    user_code=state['user_code'] or "（学生尚未提交代码）"
                )
            else:  # code_check
                mode_prompt = CODE_CHECK_PROMPT.format(
                    user_code=state['user_code'] or "（学生尚未提交代码）",
                    requirement=requirement,
                    error_history=json.dumps(state.get('error_history', []), ensure_ascii=False, indent=2)
                )

            # 组合完整的 system prompt
            # 根据模式添加工具说明
            if mode == "code_check":
                available_tools_desc = """
# 可用工具（代码检查模式）

你只能使用以下工具：
- **code_validator**: 验证用户代码的语法、逻辑和语义正确性
- **hint_generator**: 根据当前上下文和hint_level生成引导性问题
- **get_state**: 获取当前会话状态信息

注意：代码检查模式下不能使用 task_decomposer 和 progress_evaluator 工具。
"""
            else:  # requirement_guide
                available_tools_desc = """
# 可用工具（需求引导模式）

你可以使用以下工具：
- **task_decomposer**: 将用户需求拆解为具体的实现步骤
- **code_validator**: 验证用户代码的语法、逻辑和语义正确性
- **hint_generator**: 根据当前上下文和hint_level生成引导性问题
- **progress_evaluator**: 评估当前步骤是否完成，是否可以进入下一步
- **get_state**: 获取当前会话状态信息
"""

            system_prompt = f"""{base_system_prompt}

{available_tools_desc}

{mode_prompt}

# 工具调用格式

当你需要调用工具时，严格使用以下格式：

Action: 工具名称
Action Input: {{"参数名": "参数值"}}

例如：
Action: get_state
Action Input: {{"info_type": "all"}}

Action: task_decomposer
Action Input: {{"requirement": "编写程序计算1到100的和"}}

Action: progress_evaluator
Action Input: {{}}

Action: hint_generator
Action Input: {{"context": "学生想了解变量定义", "hint_level": 1, "mode": "requirement_guide", "focus_area": "数据段定义"}}

# 重要：何时让用户写代码 vs 何时提问

**直接让用户写代码的情况（不要提问）：**
1. 刚拆解完任务步骤后 → 说"现在请完成第一步的代码实现"
2. 当前步骤完成，进入下一步 → 说"很好！请继续完成下一步的代码"
3. 学生回答了问题但还没写代码 → 说"请开始实现这一步的代码"
4. 学生还没有开始写代码 → 说"请开始实现这一步的代码"

**通过问题引导的情况：**
1. 学生提交了代码但有错误 → 使用 hint_generator 生成引导问题
2. 学生的实现思路有问题 → 使用 hint_generator 生成引导问题

记住：不要在让用户写代码的时候同时提问！
"""

            # 构建用户输入
            user_input = f"学生消息: {user_message}"
            if state['user_code']:
                user_input += f"\n\n学生代码:\n```asm\n{state['user_code']}\n```"

            # 如果检测到学生已经理解问题，添加提示
            if user_understood:
                user_input += f"\n\n[系统提示：学生似乎已经理解了问题，请直接让学生修改代码，不要继续提问]"

            # 如果检测到学生在确认代码正确性，添加提示
            if user_asking_confirmation:
                user_input += f"\n\n[系统提示：学生在询问代码是否正确。请先使用 code_validator 工具验证代码，如果代码正确，直接告诉学生'代码正确！'并结束对话，不要继续提问]"

            # 添加引导提示：如果学生回答了问题，要先肯定再继续
            user_input += f"\n\n[重要提示：如果学生的回答是正确的或有道理的，必须先简短肯定（'对'、'正确'、'是的'），然后再继续引导。不要无视学生的回答直接提问]"

            # 运行简化的 Agent
            yield {
                "type": "status",
                "content": "🤖 启动 Agent..."
            }

            agent = SimpleReActAgent(self.llm, tools, system_prompt)

            async for chunk in agent.run(user_input):
                yield chunk

            yield {
                "type": "done",
                "content": ""
            }

        except Exception as e:
            yield {
                "type": "error",
                "content": f"Agent处理失败: {str(e)}"
            }

    def _format_tools(self, tools) -> str:
        """格式化工具列表"""
        tool_desc = []
        for tool in tools:
            tool_desc.append(f"- {tool.name}: {tool.description}")
        return "\n".join(tool_desc)

    def _extract_code(self, message: str) -> Optional[str]:
        """从消息中提取代码"""
        if "```" in message:
            parts = message.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    code = part.strip()
                    if code.startswith("asm") or code.startswith("assembly"):
                        code = "\n".join(code.split("\n")[1:])
                    return code.strip()
        return None

    def _detect_give_up(self, message: str) -> bool:
        """检测用户是否主动放弃"""
        give_up_keywords = [
            "不知道", "不会", "告诉我", "直接给我",
            "答案是什么", "怎么写", "帮我写",
            "不清楚", "不懂", "不明白", "看不懂",
            "不理解", "没思路", "不太懂"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in give_up_keywords)

    def _detect_understanding(self, message: str) -> bool:
        """检测用户是否已经理解了问题"""
        understanding_keywords = [
            "好像没有", "确实没有", "没有初始化", "忘记了",
            "应该", "需要", "明白了", "理解了", "知道了",
            "是的", "对的", "正确", "没错"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in understanding_keywords)

    def _detect_confirmation(self, message: str) -> bool:
        """检测用户是否在确认代码正确性"""
        confirmation_keywords = [
            "对了吗", "对吗", "正确吗", "这样对吗", "这样可以吗",
            "这样行吗", "可以了吗", "完成了吗", "好了吗",
            "没问题吧", "有问题吗"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in confirmation_keywords)

    def _format_tool_error(self, tool_name: str, error_msg: str) -> str:
        """将技术性错误转换为友好的提示"""
        # 解析 Pydantic 验证错误
        if "validation error" in error_msg.lower():
            # 提取缺失的字段名
            import re
            missing_fields = re.findall(r'(\w+)\s+Field required', error_msg)

            if missing_fields:
                fields_str = "、".join(missing_fields)
                return f"⚠️ 系统内部错误：工具 {tool_name} 缺少必要参数 ({fields_str})，正在自动修复..."
            else:
                return f"⚠️ 系统内部错误：工具 {tool_name} 参数格式不正确，正在自动修复..."

        # 其他错误
        return f"⚠️ 系统内部错误：{error_msg}"
