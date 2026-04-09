"""
数据模型定义 - 定义所有 Pydantic 模型用于请求和响应的数据验证
"""

from pydantic import BaseModel
from typing import Optional

# BaseModel 用于请求参数校验 - 数据结构定义
class SettingsRequest(BaseModel):
    """模型配置请求（用于快速设置）"""
    api_key: str
    model_name: str = 'qwen3-max'
    provider: str = 'qwen'
    base_url: str


class ConfigRequest(BaseModel):
    """完整的模型配置请求（用于配置管理）"""
    name: str
    provider: str = 'qwen'
    base_url: str
    api_key: str
    model_name: str = 'qwen3-max'
    set_active: bool = True


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: Optional[int] = None
    mode: str = 'answer'
    samplingParams: Optional[dict] = None
    current_code: Optional[str] = None  # 当前编辑器代码
    use_agent: bool = False  # 是否使用 Agent 模式
    