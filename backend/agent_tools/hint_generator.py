"""
Hint Generator - 引导性问题生成工具
根据上下文和提示强度生成苏格拉底式引导问题
"""
from typing import Dict, List
import random


class HintGenerator:
    """生成不同强度的引导性问题"""

    # 不同强度的问题模板
    LEVEL_0_TEMPLATES = [
        "你能描述一下你想实现什么功能吗？",
        "这段代码的目的是什么？",
        "你对这个问题的理解是什么？",
        "能说说你的思路吗？",
    ]

    LEVEL_1_TEMPLATES = [
        "你觉得这段代码的关键步骤是什么？",
        "如果要实现这个功能，需要哪些步骤？",
        "这里的逻辑是怎样的？",
        "你预期这段代码会产生什么结果？",
    ]

    LEVEL_2_TEMPLATES = [
        "注意观察 {focus_point}，你发现了什么？",
        "执行到这一步时，{register} 的值是多少？",
        "这条 {instruction} 指令会产生什么影响？",
        "为什么 {element} 会是这个值？",
    ]

    LEVEL_3_TEMPLATES = [
        "看看 {focus_point}，这里是不是有问题？",
        "比较一下你的预期值和实际值，{register} 是否符合预期？",
        "这个 {instruction} 指令的执行结果是否正确？",
        "问题可能出在 {focus_point}，你能找到吗？",
    ]

    @staticmethod
    def generate(context: Dict, hint_level: int = 0) -> str:
        """
        生成引导性问题

        参数：
            context: 上下文信息
                {
                    "mode": "guide" | "debug",
                    "code": "...",
                    "user_message": "...",
                    "analysis": {...},  # 代码分析结果
                    "trace": [...],     # 执行 trace（如果有）
                    "student_progress": {...}
                }
            hint_level: 提示强度 (0-3)
                0: 最弱，只问开放性问题
                1: 引导思考方向
                2: 指向具体元素
                3: 最强，几乎指出问题所在

        返回：
            引导性问题字符串
        """
        mode = context.get("mode", "guide")
        hint_level = max(0, min(3, hint_level))  # 限制在 0-3

        if mode == "debug":
            return HintGenerator._generate_debug_hint(context, hint_level)
        else:
            return HintGenerator._generate_guide_hint(context, hint_level)

    @staticmethod
    def _generate_guide_hint(context: Dict, hint_level: int) -> str:
        """生成引导模式的问题"""
        if hint_level == 0:
            return random.choice(HintGenerator.LEVEL_0_TEMPLATES)

        elif hint_level == 1:
            return random.choice(HintGenerator.LEVEL_1_TEMPLATES)

        elif hint_level == 2:
            # 从代码分析中提取关键点
            analysis = context.get("analysis", {})
            focus_points = []

            if analysis.get("stats", {}).get("used_registers"):
                focus_points.append("寄存器的使用")

            if analysis.get("warnings"):
                focus_points.append("可能存在的问题")

            focus_point = random.choice(focus_points) if focus_points else "代码逻辑"

            template = random.choice(HintGenerator.LEVEL_2_TEMPLATES)
            return template.format(
                focus_point=focus_point,
                register="AX",
                instruction="MOV",
                element="这个值"
            )

        else:  # level 3
            analysis = context.get("analysis", {})
            focus_point = "代码的某个部分"

            if analysis.get("errors"):
                focus_point = "语法"
            elif analysis.get("warnings"):
                focus_point = "逻辑"

            template = random.choice(HintGenerator.LEVEL_3_TEMPLATES)
            return template.format(
                focus_point=focus_point,
                register="AX",
                instruction="MOV"
            )

    @staticmethod
    def _generate_debug_hint(context: Dict, hint_level: int) -> str:
        """生成调试模式的问题"""
        trace = context.get("trace", [])
        analysis = context.get("analysis", {})

        if hint_level == 0:
            return "执行这段代码后，结果是否符合你的预期？"

        elif hint_level == 1:
            return "能逐步说说每条指令执行后会发生什么吗？"

        elif hint_level == 2:
            # 从 trace 中提取关键信息
            if trace and len(trace) > 0:
                # 找到有寄存器变化的步骤
                for step in trace:
                    if step.get("register_diff"):
                        reg_diff = step.get("register_diff", "")
                        instruction = step.get("instruction", "")
                        return f"执行 {instruction} 后，寄存器发生了什么变化？你预期的是什么？"

            return "观察寄存器的变化，哪一步的结果和你预期的不一样？"

        else:  # level 3
            # 最强提示，几乎指出问题
            if trace and len(trace) > 0:
                # 找到可能有问题的步骤
                for i, step in enumerate(trace):
                    instruction = step.get("instruction", "")
                    if "jmp" in instruction.lower() or "je" in instruction.lower():
                        return f"第 {i+1} 步的跳转指令是否按预期执行了？检查一下条件是否满足。"

            if analysis.get("errors"):
                return f"代码中有语法错误：{analysis['errors'][0]}，你能找到并修正吗？"

            return "问题可能出在某条指令的操作数上，仔细检查每个寄存器的值是否正确。"


# 工具函数，供 LangChain Agent 调用
def generate_hint(context: dict, hint_level: int = 0) -> str:
    """生成引导性问题（供 Agent 调用）"""
    return HintGenerator.generate(context, hint_level)
