"""
Agent Core - ReAct 架构的 AI Agent 核心
实现 Plan → Execute → Observe 循环，集成所有工具
"""
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent as create_langchain_agent
from langchain.agents.middleware.tool_call_limit import ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from typing import Any

# 导入工具
from agent_tools.student_tree import get_student_progress, update_student_progress
from agent_tools.code_analyzer import analyze_code
from agent_tools.code_executor import execute_code, get_execution_trace
from agent_tools.step_explainer import explain_step, explain_trace
from agent_tools.hint_generator import generate_hint

# 导入提示词
from agent_prompts.system_prompt import AGENT_SYSTEM_PROMPT
from agent_prompts.mode_prompt import get_mode_prompt
from agent_prompts.tool_prompt import TOOL_DESCRIPTIONS
from agent_prompts.task_prompt import build_task_prompt


class AssemblyTeachingAgent:
    """8086 汇编教学 AI Agent"""

    def __init__(self, api_key: str, model_name: str, base_url: str):
        """
        初始化 Agent

        参数：
            api_key: API Key
            model_name: 模型名称
            base_url: API Base URL
        """
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7
        )

        # 定义工具
        self.tools = self._create_tools()

        # 创建 LangChain v1 Agent
        self.agent = self._create_agent()

    def _create_tools(self) -> list:
        """创建工具列表"""
        return [
            StructuredTool.from_function(
                name="get_student_progress",
                func=get_student_progress,
                description="获取学生的学习进度和理解程度。输入：session_id（会话ID）。返回：学生状态字典。"
            ),
            StructuredTool.from_function(
                name="update_student_progress",
                func=update_student_progress,
                description="更新学生的学习进度。输入：session_id、topic、question、answered、hint_level。"
            ),
            StructuredTool.from_function(
                name="analyze_code",
                func=analyze_code,
                description="静态分析汇编代码，识别潜在问题。输入：汇编代码字符串。返回：分析结果字典。"
            ),
            StructuredTool.from_function(
                name="execute_code",
                func=execute_code,
                description="执行8086汇编代码并记录trace。输入：code、session_id。返回：execution_id。"
            ),
            StructuredTool.from_function(
                name="get_execution_trace",
                func=get_execution_trace,
                description="获取代码执行的详细trace信息。输入：execution_id。返回：trace数据列表。"
            ),
            StructuredTool.from_function(
                name="explain_step",
                func=explain_step,
                description="解释单步执行信息。输入：step_data。返回：结构化解释文本。"
            ),
            StructuredTool.from_function(
                name="explain_trace",
                func=explain_trace,
                description="解释完整的执行trace。输入：trace数据列表。返回：解释文本。"
            ),
            StructuredTool.from_function(
                name="generate_hint",
                func=generate_hint,
                description="生成引导性问题。输入：context、hint_level。返回：引导性问题。"
            ),
        ]

    def _create_agent(self):
        """创建 LangChain v1 Agent"""
        system_prompt = "\n\n".join(
            [
                AGENT_SYSTEM_PROMPT,
                TOOL_DESCRIPTIONS,
                (
                    "【输出要求】\n"
                    "- 按需调用工具，但不要向学生暴露工具调用过程或推理过程\n"
                    "- 最终只输出给学生看的中文回答\n"
                    "- 回答必须简洁，控制在 1-2 句\n"
                    "- 回答必须以引导性问题结尾\n"
                    "- 不要输出代码、伪代码、直接答案或修改方案"
                ),
            ]
        )

        return create_langchain_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
            middleware=[ToolCallLimitMiddleware(run_limit=5)],
            debug=False,
        )

    def _build_agent_input(self, mode_prompt: str, task_prompt: str) -> str:
        """构建单轮输入，让 v1 agent 在消息中拿到动态上下文"""
        return "\n\n".join(
            [
                mode_prompt,
                task_prompt,
                (
                    "请先根据需要选择工具，再给出最终回答。\n"
                    "最终回答要求：\n"
                    "1. 只能输出给学生看的内容\n"
                    "2. 只用中文，限制在 1-2 句\n"
                    "3. 必须以问题结尾\n"
                    "4. 不要输出代码、不要直接给答案"
                ),
            ]
        )

    def _extract_text(self, content: Any) -> str:
        """从 LangChain v1 的消息内容中提取纯文本"""
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                    continue

                if isinstance(block, dict):
                    text = block.get("text") or block.get("content")
                    if isinstance(text, str):
                        parts.append(text)

            return "\n".join(part.strip() for part in parts if part and part.strip())

        return ""

    def _extract_final_answer(self, result: dict) -> str:
        """从 Agent 返回的 messages 中提取最后一条 AI 文本"""
        messages = result.get("messages", [])

        for message in reversed(messages):
            if isinstance(message, AIMessage):
                content = self._extract_text(message.content)
                if content:
                    return content

        return ""

    def _prepare_agent_input(
        self,
        user_message: str,
        current_code: str,
        session_id: int,
        mode: str,
    ) -> str:
        """准备 Agent 运行输入。"""
        student_progress = get_student_progress(session_id)
        task_prompt = build_task_prompt(
            user_message=user_message,
            current_code=current_code,
            student_progress=student_progress,
            mode=mode
        )
        mode_prompt = get_mode_prompt(mode)
        return self._build_agent_input(mode_prompt, task_prompt)

    def _summarize_string(self, text: str, limit: int = 220) -> str:
        """压缩长文本，避免过程消息把对话区刷满。"""
        normalized = text.strip()
        if not normalized:
            return ""
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

    def _summarize_value(self, value: Any, key: str = "") -> str:
        """将工具参数/结果转成简短可读文本。"""
        if isinstance(value, str):
            if key in ("code", "current_code"):
                line_count = len(value.splitlines())
                return f"<代码片段，{line_count} 行，{len(value)} 字符>"
            return self._summarize_string(value)

        if isinstance(value, (int, float, bool)) or value is None:
            return str(value)

        if isinstance(value, list):
            if not value:
                return "[]"
            if len(value) <= 3:
                return self._summarize_string(json.dumps(value, ensure_ascii=False))
            return f"<列表，共 {len(value)} 项>"

        if isinstance(value, dict):
            compact = {}
            for dict_key, dict_value in list(value.items())[:5]:
                compact[dict_key] = self._summarize_value(dict_value, dict_key)
            return self._summarize_string(json.dumps(compact, ensure_ascii=False))

        return self._summarize_string(str(value))

    def _format_tool_args(self, args: Any) -> str:
        """格式化工具参数摘要。"""
        if not isinstance(args, dict) or not args:
            return "未提供参数"

        lines = []
        for key, value in args.items():
            lines.append(f"- `{key}`: {self._summarize_value(value, key)}")
        return "\n".join(lines)

    def _format_tool_output(self, output: Any) -> str:
        """格式化工具输出摘要。"""
        if output is None:
            return "无返回内容"

        if isinstance(output, str):
            return self._summarize_string(output, 260)

        if isinstance(output, (list, dict)):
            return self._summarize_value(output)

        return self._summarize_string(str(output), 260)

    def _iter_stream_messages(self, chunk: dict[str, Any]):
        """从 updates chunk 中抽取消息对象。"""
        for node_output in chunk.values():
            if not isinstance(node_output, dict):
                continue

            messages = node_output.get("messages")
            if not isinstance(messages, list):
                continue

            for message in messages:
                yield message

    def stream_process(
        self,
        user_message: str,
        current_code: str,
        session_id: int,
        mode: str = "guide"
    ):
        """
        流式产出 Agent 过程事件。

        过程消息只展示工作流和工具调用，不暴露模型隐藏推理。
        """
        tool_name_by_call_id: dict[str, str] = {}
        agent_input = self._prepare_agent_input(user_message, current_code, session_id, mode)

        for chunk in self.agent.stream(
            {"messages": [HumanMessage(content=agent_input)]},
            stream_mode="updates"
        ):
            for message in self._iter_stream_messages(chunk):
                if isinstance(message, AIMessage):
                    if message.tool_calls:
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.get("name", "unknown_tool")
                            tool_call_id = tool_call.get("id")
                            if tool_call_id:
                                tool_name_by_call_id[tool_call_id] = tool_name

                            yield {
                                "kind": "agent_step",
                                "phase": "tool_call",
                                "title": f"准备调用工具 {tool_name}",
                                "content": self._format_tool_args(tool_call.get("args", {})),
                                "status": "info",
                            }
                        continue

                    content = self._extract_text(message.content)
                    if content:
                        yield {
                            "kind": "final_answer",
                            "content": content,
                        }
                    continue

                if isinstance(message, ToolMessage):
                    tool_name = getattr(message, "name", None) or tool_name_by_call_id.get(
                        getattr(message, "tool_call_id", ""),
                        "tool"
                    )

                    yield {
                        "kind": "agent_step",
                        "phase": "tool_result",
                        "title": f"工具 {tool_name} 已返回",
                        "content": self._format_tool_output(message.content),
                        "status": "success",
                    }

    def process(
        self,
        user_message: str,
        current_code: str,
        session_id: int,
        mode: str = "guide"
    ) -> str:
        """
        处理用户输入，返回引导性回答

        参数：
            user_message: 用户消息
            current_code: 当前代码
            session_id: 会话 ID
            mode: 模式 (guide/debug)

        返回：
            引导性问题
        """
        try:
            final_answer = ""
            for event in self.stream_process(user_message, current_code, session_id, mode):
                if event.get("kind") == "final_answer":
                    final_answer = event.get("content", "")

            return final_answer or "抱歉，我无法生成合适的引导问题。"

        except Exception as e:
            print(f"[Agent] 处理失败: {e}")
            return "抱歉，处理过程中出现了错误。能再说一遍你的问题吗？"

    def detect_mode(self, user_message: str, current_code: str) -> str:
        """
        自动检测应该使用的模式

        参数：
            user_message: 用户消息
            current_code: 当前代码

        返回：
            "guide" 或 "debug"
        """
        # 简单的关键词检测
        debug_keywords = ["错误", "bug", "不对", "不工作", "问题", "调试", "为什么", "怎么回事"]
        guide_keywords = ["怎么写", "如何", "实现", "完成", "开始"]

        message_lower = user_message.lower()

        # 检查是否包含调试关键词
        for keyword in debug_keywords:
            if keyword in message_lower:
                return "debug"

        # 检查是否包含引导关键词
        for keyword in guide_keywords:
            if keyword in message_lower:
                return "guide"

        # 默认：如果有代码，倾向于 debug；否则 guide
        if current_code and len(current_code.strip()) > 0:
            return "debug"
        else:
            return "guide"


# 工具函数，供外部调用
def create_agent(api_key: str, model_name: str, base_url: str) -> AssemblyTeachingAgent:
    """创建 Agent 实例"""
    return AssemblyTeachingAgent(api_key, model_name, base_url)
