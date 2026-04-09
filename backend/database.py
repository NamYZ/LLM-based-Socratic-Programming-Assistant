"""
数据库层: database.py
"""
import sqlite3
import os
from typing import Dict
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory


def _can_write_path(path: str) -> bool:
    """判断目标数据库路径当前是否可写。"""
    expanded_path = os.path.expanduser(path)

    if os.path.exists(expanded_path):
        return os.access(expanded_path, os.W_OK)

    parent_dir = os.path.dirname(expanded_path) or '.'
    return os.path.isdir(parent_dir) and os.access(parent_dir, os.W_OK)


def _resolve_db_path() -> str:
    """优先使用用户显式配置的路径，其次选择当前环境可写的默认路径。"""
    env_path = os.environ.get("AI_CODING_TOOL_DB_PATH")
    if env_path:
        return os.path.abspath(os.path.expanduser(env_path))

    home_db_path = os.path.expanduser("~/vscode_chat.db")
    if _can_write_path(home_db_path):
        return home_db_path

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vscode_chat.db")


# 定义聊天记录存在哪个文件里（自动处理 macos & windows 路径）
DB_PATH = _resolve_db_path()

# 全局会话历史存储：为每个会话维护独立的 ChatMessageHistory（字典 = {会话ID: ChatMessageHistory 聊天历史}）
session_histories: Dict[int, ChatMessageHistory] = {}


class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """基于 SQLite 的聊天历史实现，支持持久化和内存缓存"""

    # 初始化并从数据库加载历史消息
    def __init__(self, session_id: int):
        self.session_id = session_id
        self._messages: list[BaseMessage] = [] # 空列表（BaseMessage是所有聊天消息的基类）内部私有属性
        self._load_from_db() # 内部私有方法，从数据库加载历史消息到内存

    def _load_from_db(self):
        """从数据库加载历史消息到内存"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT role, content FROM messages_vscode WHERE session_id=? ORDER BY created_at ASC",
            (self.session_id,)
        )
        rows = c.fetchall()
        conn.close()

        for role, content in rows:
            if role == 'user':
                self._messages.append(HumanMessage(content=content))
            else:
                self._messages.append(AIMessage(content=content))

    @property # 方法
    def messages(self) -> list[BaseMessage]: # 返回一个 BaseMessage 类型的列表（聊天消息列表）
        """返回消息列表"""
        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        """添加消息到历史"""
        self._messages.append(message)

    def clear(self) -> None:
        """清空历史"""
        self._messages.clear()


def get_session_history(session_id: int) -> BaseChatMessageHistory:
    """获取或创建指定会话的历史记录"""
    if session_id not in session_histories:
        session_histories[session_id] = SQLiteChatMessageHistory(session_id)
    return session_histories[session_id]


def clear_session_history(session_id: int):
    """清除指定会话的历史记录"""
    if session_id in session_histories:
        del session_histories[session_id]


def init_db():
    """初始化数据库，创建必要的表格"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
      os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 建立数据库表格：model_configs_vscode、sessions_vscode、messages_vscode、execution_traces、student_progress

    # 模型配置表，存储用户保存的 AI 模型配置（API Key、模型名称、提供商、BASE_URL等）
    c.execute('''
        CREATE TABLE IF NOT EXISTS model_configs_vscode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL DEFAULT 'qwen',
            base_url TEXT NOT NULL,
            api_key TEXT NOT NULL,
            model_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')

    # 会话表，存储每个对话会话的基本信息（标题、模式、创建和更新时间）
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions_vscode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '新对话',
            mode TEXT NOT NULL DEFAULT 'answer',
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')

    # 会话消息表，关联 sessions_vscode 表，存储每条消息的角色（用户/AI）和内容
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages_vscode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions_vscode(id) ON DELETE CASCADE
        )
    ''')

    # 8086 汇编代码执行 trace 记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS execution_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            execution_id TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            instruction TEXT NOT NULL,
            address TEXT NOT NULL,
            register_diff TEXT,
            flags_diff TEXT,
            memory_write TEXT,
            jump_info TEXT,
            created_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions_vscode(id) ON DELETE CASCADE
        )
    ''')

    # Student Tree 学习进度表
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            answered INTEGER DEFAULT 0,
            hint_level INTEGER DEFAULT 0,
            last_updated TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions_vscode(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


def get_api_key():
    """从 model_configs_vscode 表获取当前激活的配置"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT api_key, model_name, provider, base_url FROM model_configs_vscode WHERE is_active = 1 LIMIT 1")
    row = c.fetchone()
    conn.close()

    # 返回的是一个元组（配置文件中的 4 个 字段，分别是 api_key, model_name, provider, base_url）
    return (row[0], row[1], row[2], row[3]) if row else (None, None, None, None)


def get_local_time():
    """获取当前本地时间的字符串格式"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S') # 返回字符串


def auto_title(msg):
    """自动给新对话生成标题，取用户输入的前22个字符，超过部分用省略号表示"""
    t = msg.strip()[:22]
    return (t + '…') if len(msg.strip()) > 22 else t or '新对话' # 返回字符串


# 让独立工具脚本和测试脚本在首次导入时也能直接使用数据库。
init_db()
