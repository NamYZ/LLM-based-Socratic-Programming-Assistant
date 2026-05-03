"""
会话管理路由：处理对话会话的增删改查操作
"""

from fastapi import APIRouter
import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DB_PATH, clear_session_history

router = APIRouter()

@router.get("/api/sessions")
async def list_sessions():
    """从数据库中查询所有对话会话列表，按照更新时间降序排序，最多返回 60 条记录"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT s.id, s.title, s.mode, s.created_at, s.updated_at, COUNT(m.id)
        FROM sessions_vscode s LEFT JOIN messages_vscode m ON m.session_id = s.id
        GROUP BY s.id ORDER BY s.updated_at DESC LIMIT 60
    ''')
    rows = c.fetchall()
    conn.close()

    return {'sessions': [
        {'id': r[0], 'title': r[1], 'mode': r[2],
         'created_at': r[3], 'updated_at': r[4], 'msg_count': r[5]}
        for r in rows
    ]}


@router.delete("/api/sessions/{sid}")
async def delete_session(sid: int):
    """删除指定会话及其所有消息"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 先删除这个会话的所有消息
    c.execute("DELETE FROM messages_vscode WHERE session_id=?", (sid,))
    # 再删除会话本身
    c.execute("DELETE FROM sessions_vscode WHERE id=?", (sid,))

    conn.commit()
    conn.close()

    # 清除内存中的会话历史
    clear_session_history(sid)

    return {'success': True}


@router.get("/api/sessions/{sid}/messages")
async def get_session_messages(sid: int):
    """打开一个具体的聊天会话，把里面的所有聊天记录 + 会话信息取出来返回给前端"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 查询这个会话的所有消息
    c.execute("SELECT role, content, created_at FROM messages_vscode WHERE session_id=? ORDER BY created_at ASC", (sid,))
    msgs = c.fetchall()

    # 再查询这个会话的信息（标题、模式、创建时间）
    c.execute("SELECT title, mode, created_at FROM sessions_vscode WHERE id=?", (sid,))
    sess = c.fetchone()
    conn.close()

    # 会话不存在的情况，返回一个默认的"未知对话"标题和空消息列表
    if not sess:
        sess = ('未知对话', 'answer', '')
    return {
        'messages': [{'role': r[0], 'content': r[1], 'time': r[2]} for r in msgs],
        'session': {'id': sid, 'title': sess[0], 'mode': sess[1], 'created_at': sess[2] or ''}
    }


@router.delete("/api/history")
async def clear_all():
    """一键清除所有聊天记录和会话"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages_vscode")
    c.execute("DELETE FROM sessions_vscode")
    conn.commit()
    conn.close()

    # 清除所有内存中的会话历史
    from database import session_histories
    session_histories.clear()

    return {'success': True}
