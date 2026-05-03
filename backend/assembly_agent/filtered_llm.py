"""
自定义 ChatOpenAI 包装器，用于处理 reasoning_content - DeepSeek 模型的 thinking mode 要求保留 reasoning_content 在对话历史中
"""

from langchain_openai import ChatOpenAI


class FilteredChatOpenAI(ChatOpenAI):
    """
    自定义的 ChatOpenAI，处理 DeepSeek 等模型的 thinking mode

    注意：DeepSeek 的 thinking mode 要求：
    - 如果响应包含 reasoning_content，必须在后续请求中保留它
    - 不能过滤掉 reasoning_content，否则会报错
    - 我们只是不在用户界面显示它
    """

    # 不需要过滤，DeepSeek 要求保留 reasoning_content
    pass
