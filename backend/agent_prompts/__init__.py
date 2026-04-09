"""
Agent Prompts Package
包含所有 Agent 使用的提示词
"""

from .system_prompt import AGENT_SYSTEM_PROMPT
from .mode_prompt import GUIDE_MODE_PROMPT, DEBUG_MODE_PROMPT, get_mode_prompt
from .tool_prompt import TOOL_DESCRIPTIONS
from .task_prompt import build_task_prompt

__all__ = [
    'AGENT_SYSTEM_PROMPT',
    'GUIDE_MODE_PROMPT',
    'DEBUG_MODE_PROMPT',
    'get_mode_prompt',
    'TOOL_DESCRIPTIONS',
    'build_task_prompt',
]
