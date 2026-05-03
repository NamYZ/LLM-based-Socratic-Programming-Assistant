"""
LangChain-compatible tools for Assembly Teaching Agent - 将现有工具转换为标准的 LangChain Tool 格式
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from .filtered_llm import FilteredChatOpenAI
from .error_tracker import ErrorTracker
from .prompts.tool_prompts import (
    TASK_DECOMPOSER_PROMPT,
    CODE_VALIDATOR_PROMPT,
    PROGRESS_EVALUATOR_PROMPT,
    HINT_GENERATOR_PROMPT
)


class TaskDecomposerInput(BaseModel):
    """Input schema for task_decomposer tool"""
    requirement: str = Field(description="用户的需求描述，需要拆解为具体的实现步骤")


class CodeValidatorInput(BaseModel):
    """Input schema for code_validator tool"""
    code: str = Field(default="", description="需要验证的汇编代码（可选，如果不传则从状态中获取）")
    requirement: str = Field(default="", description="代码要实现的需求（可选，如果不传则从状态中获取）")
    context: str = Field(default="", description="额外的上下文信息")


class ProgressEvaluatorInput(BaseModel):
    """Input schema for progress_evaluator tool"""
    student_code: str = Field(default="", description="学生当前提交的代码（可选，如果不传则从状态中获取）")


class HintGeneratorInput(BaseModel):
    """Input schema for hint_generator tool"""
    context: str = Field(description="当前上下文（包括代码、需求、错误信息等）")
    hint_level: int = Field(description="提示深度 (1=隐晦, 2=中等, 3=明确)")
    mode: str = Field(description="当前模式 (requirement_guide 或 code_check)")
    focus_area: str = Field(default="", description="需要重点引导的方向")


class GetStateInput(BaseModel):
    """Input schema for get_state tool"""
    info_type: str = Field(description="要获取的状态信息类型: 'all', 'hint_level', 'current_step', 'user_code', 'task_steps', 'requirement'")


def create_langchain_tools(api_key: str, model_name: str, base_url: Optional[str], state_manager, session_id: int) -> List:
    """
    创建LangChain兼容的工具列表

    Args:
        api_key: OpenAI API密钥
        model_name: 模型名称
        base_url: API基础URL
        state_manager: 状态管理器实例
        session_id: 当前会话ID

    Returns:
        LangChain Tool列表
    """

    # 创建共享的LLM实例 - 使用 FilteredChatOpenAI 过滤 reasoning_content
    llm_config = {
        "model": model_name,
        "api_key": api_key,
        "temperature": 0.3,
        "store": False,  # 禁用存储功能
    }
    if base_url:
        llm_config["base_url"] = base_url

    llm = FilteredChatOpenAI(**llm_config)

    # 创建错误追踪器实例
    error_tracker = ErrorTracker()

    # ===== Task Decomposer Tool =====
    def task_decomposer_func(requirement: str) -> str:
        """将用户需求拆解为具体的实现步骤"""
        # 检查任务是否已经分解过
        state = state_manager.get_state(session_id)
        if state and state.get('task_steps'):
            return f"错误：任务已经分解完成，不能重复分解！当前任务包含{len(state['task_steps'])}个步骤。请使用 progress_evaluator 评估进度，而不是重新分解任务。"

        prompt = TASK_DECOMPOSER_PROMPT.format(requirement=requirement)
        try:
            response = llm.invoke(prompt)
            content = response.content

            # 提取JSON部分
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)
            steps = result.get("steps", [])

            # 更新状态
            state_manager.update_task_steps(session_id, steps)

            return f"任务已拆解为{len(steps)}个步骤:\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        except Exception as e:
            return f"任务拆解失败: {str(e)}"

    # ===== Code Validator Tool =====
    def code_validator_func(code: str = "", requirement: str = "", context: str = "") -> str:
        """验证用户代码的语法、逻辑和语义正确性"""
        # 从状态管理器中获取缺失的参数
        state = state_manager.get_state(session_id)
        if not state:
            return "错误：会话状态不存在，无法验证代码"

        # 使用传入的参数或状态中的参数
        code = code or state.get('user_code', '')
        requirement = requirement or state.get('requirement', '')

        if not code:
            return "错误：没有代码可供验证，请先提交代码"

        if not requirement:
            return "错误：缺少需求描述，无法验证代码是否符合要求"

        prompt = CODE_VALIDATOR_PROMPT.format(
            code=code,
            requirement=requirement,
            context=context or "无"
        )
        try:
            response = llm.invoke(prompt)
            content = response.content

            # 提取JSON部分
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)

            # 如果有错误，记录到状态
            if not result.get("is_valid", False):
                state_manager.add_error(
                    session_id,
                    result.get("error_type", "unknown"),
                    result.get("error_category", "")
                )

                # 追踪错误到错题库
                error_tracker.track_error(
                    session_id=session_id,
                    error_info={
                        'category': result.get("error_type", "unknown"),
                        'description': result.get("error_category", ""),
                        'code': code
                    }
                )

                # 检查是否连续犯同类错误（仅在非手动模式下自动增加提示等级）
                state = state_manager.get_state(session_id)
                if state and not state.get('hint_level_manual_mode'):
                    if state_manager.check_repeated_error(session_id):
                        state_manager.increase_hint_level(session_id)

            # 返回验证结果的文本描述（不直接暴露给学生）
            status = "基本正确" if result.get("is_valid", False) else "存在问题"
            return f"代码验证完成: {status}\n错误类型: {result.get('error_type', 'none')}\n引导方向: {result.get('suggestions_direction', '')}"
        except Exception as e:
            return f"代码验证失败: {str(e)}"

    # ===== Progress Evaluator Tool =====
    def progress_evaluator_func(student_code: str = "") -> str:
        """评估当前步骤是否完成"""
        # 从状态管理器中获取所有必要信息
        state = state_manager.get_state(session_id)
        if not state:
            return "错误：会话状态不存在，无法评估进度"

        # 使用传入的代码或状态中的代码
        code = student_code or state.get('user_code', '')
        current_step = state.get('current_step', 1)
        task_steps = state.get('task_steps', [])
        requirement = state.get('requirement', '')

        if not task_steps:
            return "错误：任务步骤尚未拆解，请先使用 task_decomposer 工具"

        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(task_steps)])
        current_step_desc = task_steps[current_step - 1] if 0 < current_step <= len(task_steps) else "未知步骤"

        prompt = PROGRESS_EVALUATOR_PROMPT.format(
            current_step=current_step,
            total_steps=len(task_steps),
            current_step_description=current_step_desc,
            all_steps=steps_text,
            user_code=code or "（学生尚未提交代码）",
            requirement=requirement
        )
        try:
            response = llm.invoke(prompt)
            content = response.content

            # 提取JSON部分
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)

            # 如果当前步骤完成，自动移动到下一步
            if result.get("is_completed", False):
                state = state_manager.get_state(session_id)
                if state and state['current_step'] < len(task_steps):
                    state_manager.move_to_next_step(session_id)
                    state_manager.reset_hint_level(session_id)

                    # 检查是否所有步骤都已完成
                    updated_state = state_manager.get_state(session_id)
                    if updated_state and updated_state['current_step'] >= len(task_steps):
                        # 所有步骤完成，标记为已完成
                        state_manager.mark_completed(session_id)
                        return f"恭喜！所有步骤已完成！任务已成功完成。"

                    return f"当前步骤已完成！已自动进入下一步: {task_steps[updated_state['current_step']]}"
                elif state and state['current_step'] >= len(task_steps):
                    # 已经是最后一步，标记为完成
                    state_manager.mark_completed(session_id)
                    return f"恭喜！所有步骤已完成！任务已成功完成。"

            return f"进度评估: {'已完成' if result.get('is_completed', False) else '未完成'}\n完成度: {result.get('completion_rate', 0)*100}%\n建议: {result.get('next_action', 'continue_current')}"
        except Exception as e:
            return f"进度评估失败: {str(e)}"

    # ===== Hint Generator Tool =====
    def hint_generator_func(context: str, hint_level: int, mode: str, focus_area: str = "") -> str:
        """生成引导性问题"""
        mode_name = "需求引导模式" if mode == "requirement_guide" else "代码检查模式"

        prompt = HINT_GENERATOR_PROMPT.format(
            context=context,
            mode_name=mode_name,
            hint_level=hint_level,
            focus_area=focus_area or "无特定方向"
        )
        try:
            response = llm.invoke(prompt)
            question = response.content.strip()

            # 确保以问号结尾
            if not question.endswith('？') and not question.endswith('?'):
                question += '？'

            return question
        except Exception as e:
            return "请仔细思考一下，你的代码实现了什么功能？"

    # ===== Get State Tool =====
    def get_state_func(info_type: str) -> str:
        """获取当前会话状态信息"""
        state = state_manager.get_state(session_id)
        if not state:
            return "会话状态不存在"

        if info_type == "all":
            return f"""当前会话状态:
- 模式: {state['mode']}
- 当前步骤: {state['current_step']}/{len(state['task_steps'])}
- Hint Level: {state['hint_level']}
- 是否有代码: {'是' if state['user_code'] else '否'}
- 任务步骤数: {len(state['task_steps'])}
"""
        elif info_type == "hint_level":
            return f"当前Hint Level: {state['hint_level']}"
        elif info_type == "current_step":
            return f"当前步骤: 第{state['current_step']}/{len(state['task_steps'])}步"
        elif info_type == "user_code":
            return f"用户代码:\n```asm\n{state['user_code'] or '（无）'}\n```"
        elif info_type == "task_steps":
            if state['task_steps']:
                steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(state['task_steps'])])
                return f"任务步骤:\n{steps_text}"
            return "任务步骤尚未拆解"
        elif info_type == "requirement":
            return f"需求: {state['requirement']}"
        else:
            return f"未知的信息类型: {info_type}"

    # 创建LangChain Tool对象
    tools = [
        StructuredTool.from_function(
            func=task_decomposer_func,
            name="task_decomposer",
            description="将用户需求拆解为3-7个具体的实现步骤。适用于需求引导模式的初始阶段。",
            args_schema=TaskDecomposerInput
        ),
        StructuredTool.from_function(
            func=code_validator_func,
            name="code_validator",
            description="验证用户代码的语法、逻辑和语义正确性。返回验证结果供内部决策使用，不要直接告诉学生。会自动从状态中获取代码和需求，你可以不传参数或只传 code。",
            args_schema=CodeValidatorInput
        ),
        StructuredTool.from_function(
            func=progress_evaluator_func,
            name="progress_evaluator",
            description="评估当前步骤是否完成，是否可以进入下一步。如果完成会自动移动到下一步。会自动从状态中获取所有必要信息（current_step、task_steps、requirement），你只需要传入 student_code（可选）。",
            args_schema=ProgressEvaluatorInput
        ),
        StructuredTool.from_function(
            func=hint_generator_func,
            name="hint_generator",
            description="根据当前上下文和hint_level生成苏格拉底式引导问题。这是你与学生交互的主要方式。必须传入：context（上下文文本）、hint_level（提示等级）、mode（模式）、focus_area（引导方向）。",
            args_schema=HintGeneratorInput
        ),
        StructuredTool.from_function(
            func=get_state_func,
            name="get_state",
            description="获取当前会话状态信息（hint_level、current_step、user_code等）。在决策前先查询状态。",
            args_schema=GetStateInput
        )
    ]

    return tools
