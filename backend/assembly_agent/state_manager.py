"""
State Manager for Assembly Teaching Agent - 管理会话状态：任务进度、用户代码、当前引导步骤、HintLevel、错误历史
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from database import DB_PATH


class AgentStateManager:
    """管理Assembly Teaching Agent的会话状态

    注意：数据库表的创建已在 database.py 的 init_db() 中完成
    """

    def _default_conversation_context(self) -> Dict[str, Any]:
        """默认的结构化对话上下文"""
        return {
            'turns': [],
            'last_user_message': '',
            'last_agent_reply': '',
            'last_step': 0,
            'last_hint_level': 1,
            'confusion_count': 0,
            'repeat_reply_count': 0,
            'last_confusion_status': '',
            'last_confusion_reason': '',
            'last_guidance_strategy': ''
        }

    def _deserialize_conversation_context(self, raw_value: str) -> Dict[str, Any]:
        """将数据库中的对话上下文解析为结构化对象"""
        default_context = self._default_conversation_context()

        if not raw_value:
            return default_context

        try:
            context = json.loads(raw_value)
            if not isinstance(context, dict):
                return default_context
        except Exception:
            # 兼容旧数据：如果之前存的是普通字符串，保留为最后一轮回复摘要
            context = {'last_agent_reply': raw_value}

        normalized = default_context.copy()
        normalized.update(context)

        turns = normalized.get('turns', [])
        if not isinstance(turns, list):
            normalized['turns'] = []
        else:
            normalized['turns'] = turns[-8:]

        return normalized

    def get_state(self, session_id: int) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT mode, task_steps, current_step, user_code, hint_level,
                   error_history, conversation_context, requirement,
                   hint_level_manual_mode, total_steps, completion_status
            FROM assembly_agent_sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'mode': row[0],
            'task_steps': json.loads(row[1]) if row[1] else [],
            'current_step': row[2],
            'user_code': row[3],
            'hint_level': row[4],
            'error_history': json.loads(row[5]) if row[5] else [],
            'conversation_context': self._deserialize_conversation_context(row[6]),
            'requirement': row[7],
            'hint_level_manual_mode': row[8] if len(row) > 8 else 0,
            'total_steps': row[9] if len(row) > 9 else 0,
            'completion_status': row[10] if len(row) > 10 else 'in_progress'
        }

    def create_session(self, session_id: int, mode: str, requirement: str = '') -> Dict[str, Any]:
        """创建新的会话状态"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO assembly_agent_sessions
            (session_id, mode, requirement, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, mode, requirement, now, now))

        conn.commit()
        conn.close()

        return {
            'mode': mode,
            'task_steps': [],
            'current_step': 0,
            'user_code': '',
            'hint_level': 1,
            'error_history': [],
            'conversation_context': self._default_conversation_context(),
            'requirement': requirement
        }

    def update_state(self, session_id: int, updates: Dict[str, Any]):
        """更新会话状态"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 构建更新语句
        set_clauses = []
        values = []

        for key, value in updates.items():
            if key in ['task_steps', 'error_history', 'conversation_context']:
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value, ensure_ascii=False))
            else:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        set_clauses.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(session_id)

        sql = f"UPDATE assembly_agent_sessions SET {', '.join(set_clauses)} WHERE session_id = ?"
        cursor.execute(sql, values)

        conn.commit()
        conn.close()

    def update_code(self, session_id: int, code: str):
        """更新用户代码"""
        self.update_state(session_id, {'user_code': code})

    def update_task_steps(self, session_id: int, steps: List[str]):
        """更新任务步骤"""
        state = self.get_state(session_id)
        updates: Dict[str, Any] = {'task_steps': steps, 'total_steps': len(steps)}

        # 任务第一次拆解完成后，立即进入第 1 步
        if steps and (not state or state.get('current_step', 0) <= 0):
            updates['current_step'] = 1

        self.update_state(session_id, updates)

    def move_to_next_step(self, session_id: int):
        """移动到下一步"""
        state = self.get_state(session_id)
        if state:
            self.update_state(session_id, {'current_step': state['current_step'] + 1})

    def increase_hint_level(self, session_id: int, amount: int = 1):
        """提升 hint_level（最大3）"""
        state = self.get_state(session_id)
        if state and state['hint_level'] < 3:
            next_level = min(3, state['hint_level'] + max(1, amount))
            self.update_state(session_id, {'hint_level': next_level})

    def set_hint_level(self, session_id: int, level: int):
        """直接设置 hint_level（自动限制在1-3）"""
        clamped_level = max(1, min(3, level))
        self.update_state(session_id, {'hint_level': clamped_level})

    def reset_hint_level(self, session_id: int):
        """重置 hint_level 为1"""
        self.update_state(session_id, {'hint_level': 1})

    def add_error(self, session_id: int, error_type: str, error_category: str):
        """添加错误记录"""
        state = self.get_state(session_id)
        if state:
            error_history = state['error_history']
            error_history.append({
                'type': error_type,
                'category': error_category,
                'timestamp': datetime.now().isoformat()
            })

            # 只保留最近10条错误记录
            if len(error_history) > 10:
                error_history = error_history[-10:]

            self.update_state(session_id, {'error_history': error_history})

    def check_repeated_error(self, session_id: int) -> bool:
        """检查是否连续2次犯同类错误"""
        state = self.get_state(session_id)
        if not state or len(state['error_history']) < 2:
            return False

        # 检查最近两次错误是否同类
        recent_errors = state['error_history'][-2:]
        return recent_errors[0]['category'] == recent_errors[1]['category']

    def update_conversation_context(self, session_id: int, context: Dict[str, Any]):
        """更新对话上下文"""
        self.update_state(session_id, {'conversation_context': context})

    def get_or_create_state(self, session_id: int, mode: str, requirement: str = '') -> Dict[str, Any]:
        """获取或创建会话状态"""
        state = self.get_state(session_id)
        if state is None:
            state = self.create_session(session_id, mode, requirement)
        return state

    def set_manual_hint_mode(self, session_id: int, enabled: bool):
        """启用/禁用手动提示等级模式"""
        self.update_state(session_id, {'hint_level_manual_mode': 1 if enabled else 0})

    def set_hint_level_manual(self, session_id: int, level: int):
        """手动设置提示等级（仅在手动模式下生效）"""
        state = self.get_state(session_id)
        if state and state.get('hint_level_manual_mode') == 1:
            # 限制在1-3范围内
            clamped_level = max(1, min(3, level))
            self.update_state(session_id, {'hint_level': clamped_level})
            return True
        return False

    def mark_completed(self, session_id: int):
        """标记会话为已完成"""
        self.update_state(session_id, {'completion_status': 'completed'})

    def get_progress_info(self, session_id: int) -> Dict[str, Any]:
        """获取进度信息用于UI显示"""
        state = self.get_state(session_id)
        if not state:
            return {
                'current_step': 0,
                'total_steps': 0,
                'task_steps': [],
                'hint_level': 1,
                'manual_mode': False,
                'completion_status': 'in_progress'
            }

        task_steps = state.get('task_steps', [])
        current_step = state.get('current_step', 0)
        completed_steps = len(task_steps) if state.get('completion_status') == 'completed' else max(0, current_step - 1)
        return {
            'current_step': current_step,
            'completed_steps': completed_steps,
            'total_steps': len(task_steps),
            'task_steps': task_steps,
            'hint_level': state.get('hint_level', 1),
            'manual_mode': state.get('hint_level_manual_mode', 0) == 1,
            'completion_status': state.get('completion_status', 'in_progress')
        }
