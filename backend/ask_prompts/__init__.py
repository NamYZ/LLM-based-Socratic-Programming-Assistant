"""
ask_prompts ：包含答案式和引导式的提示词
"""

from .guided_mode_prompts import GUIDED_SYSTEM_PROMPT
from .question_mode_prompts import ANSWER_SYSTEM_PROMPT

__all__ = ['GUIDED_SYSTEM_PROMPT', 'ANSWER_SYSTEM_PROMPT']
