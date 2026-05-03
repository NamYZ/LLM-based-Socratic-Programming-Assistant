"""
Assembly Teaching Agent Module - 基于 LangChain + 简化ReAct实现 + 苏格拉底式引导法的8086汇编教学Agent
"""

# 导出简化版 Agent（推荐使用，避免 reasoning_content 问题）
from .simple_agent import AssemblyTeachingAgentSimple

# Simple Agent 完全控制流程，可以正确处理 reasoning_content
AssemblyTeachingAgent = AssemblyTeachingAgentSimple

__all__ = [
    'AssemblyTeachingAgent',
    'AssemblyTeachingAgentSimple',
    'AssemblyTeachingAgentLangChain',
    'create_assembly_agent_langchain'
]
