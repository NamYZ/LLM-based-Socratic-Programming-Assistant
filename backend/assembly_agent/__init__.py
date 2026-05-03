"""
Assembly Teaching Agent Module
基于LangChain + 简化ReAct实现 + 苏格拉底式引导法的8086汇编教学Agent
"""

# 导出简化版 Agent（推荐使用，避免 reasoning_content 问题）
from .simple_agent import AssemblyTeachingAgentSimple

# 导出LangChain版本的Agent（可能有 reasoning_content 问题）
from .agent_core_langchain import AssemblyTeachingAgentLangChain, create_assembly_agent_langchain

# 默认使用简化版（避免 LangChain 的 reasoning_content 问题）
# LangChain 的 create_agent 在内部会处理消息，导致 DeepSeek 的 reasoning_content 丢失
# Simple Agent 完全控制流程，可以正确处理 reasoning_content
AssemblyTeachingAgent = AssemblyTeachingAgentSimple

__all__ = [
    'AssemblyTeachingAgent',
    'AssemblyTeachingAgentSimple',
    'AssemblyTeachingAgentLangChain',
    'create_assembly_agent_langchain'
]
