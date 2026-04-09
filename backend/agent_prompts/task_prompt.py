"""
Agent 任务提示词：动态生成，包含当前代码、用户输入、学生状态等上下文信息
"""

def build_task_prompt(
    user_message: str,
    current_code: str = "",
    student_progress: dict = None,
    trace_analysis: str = "",
    mode: str = "guide"
) -> str:
    """
    构建任务提示词

    参数：
        user_message: 用户的输入消息
        current_code: 当前编辑器中的代码
        student_progress: 学生的学习进度数据
        trace_analysis: trace 分析结果（如果有）
        mode: 当前模式 (guide/debug)
    """

    prompt_parts = ["【当前任务】\n"]

    # 用户输入
    prompt_parts.append(f"学生说：{user_message}\n")

    # 当前代码
    if current_code:
        prompt_parts.append(f"\n【当前代码】\n```asm\n{current_code}\n```\n")

    # 学生进度
    if student_progress:
        prompt_parts.append("\n【学生状态】\n")
        if student_progress.get("topics"):
            prompt_parts.append(f"已学习主题：{', '.join(student_progress['topics'])}\n")
        if student_progress.get("current_hint_level") is not None:
            prompt_parts.append(f"当前提示强度：{student_progress['current_hint_level']}/3\n")
        if student_progress.get("answered_questions"):
            prompt_parts.append(f"已回答问题数：{student_progress['answered_questions']}\n")

    # Trace 分析（debug 模式）
    if trace_analysis:
        prompt_parts.append(f"\n【执行分析】\n{trace_analysis}\n")

    # 任务指示
    prompt_parts.append("\n【你的任务】\n")
    if mode == "debug":
        prompt_parts.append(
            "1. 分析代码执行过程和 trace 信息\n"
            "2. 识别问题所在（不要直接告诉学生）\n"
            "3. 生成引导性问题，帮助学生自己发现问题\n"
            "4. 根据学生的理解程度调整提示强度\n"
        )
    else:
        prompt_parts.append(
            "1. 理解学生想要实现的功能\n"
            "2. 评估当前代码的完成度和方向\n"
            "3. 生成引导性问题，帮助学生继续前进\n"
            "4. 不要给出代码，只提供思路方向\n"
        )

    return "".join(prompt_parts)
