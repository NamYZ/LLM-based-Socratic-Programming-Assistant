"""
Teaching Strategy - 教学策略管理
根据学生的回答质量和理解程度动态调整教学策略
"""
from typing import Dict, Optional
import re


class TeachingStrategy:
    """教学策略管理器"""

    @staticmethod
    def analyze_student_response(
        user_message: str,
        expected_concepts: list = None,
        previous_hint_level: int = 0
    ) -> Dict:
        """
        分析学生的回答质量

        参数：
            user_message: 学生的回答
            expected_concepts: 期望学生理解的概念列表
            previous_hint_level: 之前的提示强度

        返回：
            {
                "quality": "good" | "partial" | "poor" | "confused",
                "understood_concepts": [...],
                "suggested_hint_level": 0-3,
                "needs_encouragement": bool,
                "teaching_action": "continue" | "clarify" | "increase_hint" | "redirect"
            }
        """
        message_lower = user_message.lower()

        # 检测困惑信号
        confusion_signals = [
            "不懂", "不明白", "不理解", "不知道", "看不懂",
            "什么意思", "怎么回事", "为什么", "confused", "don't understand"
        ]
        is_confused = any(signal in message_lower for signal in confusion_signals)

        # 检测进步信号
        progress_signals = [
            "明白了", "懂了", "理解了", "知道了", "原来",
            "我觉得", "应该是", "可能是", "是不是", "understand", "got it"
        ]
        shows_progress = any(signal in message_lower for signal in progress_signals)

        # 检测错误理解
        wrong_signals = [
            "错了", "不对", "失败", "不行", "还是不对"
        ]
        acknowledges_error = any(signal in message_lower for signal in wrong_signals)

        # 分析回答长度和深度
        word_count = len(user_message)
        has_technical_terms = TeachingStrategy._contains_technical_terms(user_message)

        # 判断回答质量
        if is_confused and word_count < 20:
            quality = "confused"
            suggested_hint_level = min(previous_hint_level + 1, 3)
            teaching_action = "increase_hint"
        elif shows_progress and has_technical_terms:
            quality = "good"
            suggested_hint_level = max(previous_hint_level - 1, 0)
            teaching_action = "continue"
        elif shows_progress or word_count > 30:
            quality = "partial"
            suggested_hint_level = previous_hint_level
            teaching_action = "clarify"
        else:
            quality = "poor"
            suggested_hint_level = min(previous_hint_level + 1, 3)
            teaching_action = "increase_hint"

        # 检查是否需要鼓励
        needs_encouragement = acknowledges_error or is_confused or quality == "poor"

        # 识别理解的概念
        understood_concepts = []
        if expected_concepts:
            for concept in expected_concepts:
                if concept.lower() in message_lower:
                    understood_concepts.append(concept)

        return {
            "quality": quality,
            "understood_concepts": understood_concepts,
            "suggested_hint_level": suggested_hint_level,
            "needs_encouragement": needs_encouragement,
            "teaching_action": teaching_action
        }

    @staticmethod
    def _contains_technical_terms(text: str) -> bool:
        """检查是否包含技术术语"""
        technical_terms = [
            "寄存器", "ax", "bx", "cx", "dx", "si", "di", "bp", "sp",
            "标志位", "零标志", "进位", "溢出", "符号位",
            "mov", "add", "sub", "jmp", "je", "jne", "cmp",
            "堆栈", "内存", "地址", "指令", "操作数",
            "register", "flag", "stack", "memory", "instruction"
        ]
        text_lower = text.lower()
        return any(term in text_lower for term in technical_terms)

    @staticmethod
    def should_execute_code(
        user_message: str,
        current_code: str,
        mode: str
    ) -> bool:
        """
        判断是否应该执行代码

        参数：
            user_message: 学生消息
            current_code: 当前代码
            mode: 当前模式

        返回：
            是否应该执行代码
        """
        # 如果没有代码，不执行
        if not current_code or len(current_code.strip()) < 10:
            return False

        message_lower = user_message.lower()

        # 明确要求执行的关键词
        execute_keywords = [
            "运行", "执行", "结果", "输出", "trace",
            "为什么不对", "哪里错了", "出了什么问题",
            "run", "execute", "result", "output"
        ]

        # 调试模式下更倾向于执行
        if mode == "debug":
            debug_keywords = ["错误", "bug", "不工作", "不对", "问题"]
            if any(kw in message_lower for kw in debug_keywords):
                return True

        return any(kw in message_lower for kw in execute_keywords)

    @staticmethod
    def determine_focus_area(
        analysis_result: Dict,
        trace_data: list = None
    ) -> Dict:
        """
        确定教学重点区域

        参数：
            analysis_result: 代码分析结果
            trace_data: 执行trace数据

        返回：
            {
                "focus_type": "syntax" | "logic" | "execution" | "concept",
                "focus_details": {...},
                "teaching_approach": "..."
            }
        """
        # 如果有语法错误，优先处理
        if analysis_result.get("errors"):
            return {
                "focus_type": "syntax",
                "focus_details": {
                    "errors": analysis_result["errors"][:2]  # 只关注前2个错误
                },
                "teaching_approach": "引导学生观察错误信息，理解语法规则"
            }

        # 如果有警告，关注逻辑问题
        if analysis_result.get("warnings"):
            return {
                "focus_type": "logic",
                "focus_details": {
                    "warnings": analysis_result["warnings"][:2]
                },
                "teaching_approach": "引导学生思考潜在的逻辑问题"
            }

        # 如果有trace数据，关注执行过程
        if trace_data and len(trace_data) > 0:
            # 找到关键步骤（寄存器变化大、跳转指令等）
            key_steps = []
            for i, step in enumerate(trace_data):
                if step.get("register_diff") or step.get("jump_info"):
                    key_steps.append(i)

            return {
                "focus_type": "execution",
                "focus_details": {
                    "total_steps": len(trace_data),
                    "key_steps": key_steps[:3]  # 最多3个关键步骤
                },
                "teaching_approach": "引导学生逐步观察执行过程中的变化"
            }

        # 默认：概念理解
        return {
            "focus_type": "concept",
            "focus_details": {},
            "teaching_approach": "引导学生理解基本概念和思路"
        }

    @staticmethod
    def generate_encouragement(quality: str, hint_level: int) -> Optional[str]:
        """
        生成鼓励语句

        参数：
            quality: 回答质量
            hint_level: 当前提示强度

        返回：
            鼓励语句（如果需要）
        """
        if quality == "good":
            return "很好的思考！"
        elif quality == "partial":
            return "你的方向是对的。"
        elif quality == "confused" and hint_level < 2:
            return "没关系，我们一步步来。"
        elif quality == "poor" and hint_level >= 2:
            return "让我换个角度帮你理解。"
        return None


# 工具函数，供 Agent 调用
def analyze_student_response(
    user_message: str,
    expected_concepts: list = None,
    previous_hint_level: int = 0
) -> dict:
    """分析学生回答质量（供 Agent 调用）"""
    return TeachingStrategy.analyze_student_response(
        user_message, expected_concepts, previous_hint_level
    )


def should_execute_code(user_message: str, current_code: str, mode: str) -> bool:
    """判断是否应该执行代码（供 Agent 调用）"""
    return TeachingStrategy.should_execute_code(user_message, current_code, mode)
