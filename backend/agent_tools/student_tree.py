"""
Student Tree - 学生学习进度管理工具
跟踪学生的学习状态、已回答的问题、提示强度等
"""
import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import DB_PATH, get_local_time


class StudentTree:
    """管理学生学习进度的工具类"""

    @staticmethod
    def get_progress(session_id: int) -> dict:
        """
        获取学生的学习进度

        参数：
            session_id: 会话 ID

        返回：
            {
                "topics": ["主题1", "主题2"],  # 已学习的主题
                "answered_questions": 5,  # 已回答的问题数
                "current_hint_level": 1,  # 当前提示强度 (0-3)
                "recent_topics": [...]  # 最近学习的主题
            }
        """
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # 获取所有进度记录
        c.execute("""
            SELECT topic, question, answered, hint_level, last_updated
            FROM student_progress
            WHERE session_id = ?
            ORDER BY last_updated DESC
        """, (session_id,))

        rows = c.fetchall()
        conn.close()

        if not rows:
            return {
                "topics": [],
                "answered_questions": 0,
                "current_hint_level": 0,
                "recent_topics": []
            }

        # 统计数据
        topics = set()
        answered_count = 0
        hint_levels = []
        recent_topics = []

        for topic, question, answered, hint_level, last_updated in rows:
            topics.add(topic)
            if answered:
                answered_count += 1
            hint_levels.append(hint_level)
            if len(recent_topics) < 3:
                recent_topics.append(topic)

        # 计算平均提示强度
        avg_hint_level = sum(hint_levels) // len(hint_levels) if hint_levels else 0

        return {
            "topics": list(topics),
            "answered_questions": answered_count,
            "current_hint_level": avg_hint_level,
            "recent_topics": recent_topics
        }

    @staticmethod
    def update_progress(
        session_id: int,
        topic: str,
        question: str,
        answered: bool = False,
        hint_level: int = 0
    ) -> bool:
        """
        更新学生的学习进度

        参数：
            session_id: 会话 ID
            topic: 主题（如 "寄存器操作", "跳转指令"）
            question: 问题内容
            answered: 是否已回答
            hint_level: 提示强度 (0-3)

        返回：
            是否更新成功
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # 检查是否已存在相同的问题
            c.execute("""
                SELECT id FROM student_progress
                WHERE session_id = ? AND topic = ? AND question = ?
            """, (session_id, topic, question))

            existing = c.fetchone()

            if existing:
                # 更新现有记录
                c.execute("""
                    UPDATE student_progress
                    SET answered = ?, hint_level = ?, last_updated = ?
                    WHERE id = ?
                """, (1 if answered else 0, hint_level, get_local_time(), existing[0]))
            else:
                # 插入新记录
                c.execute("""
                    INSERT INTO student_progress
                    (session_id, topic, question, answered, hint_level, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, topic, question, 1 if answered else 0, hint_level, get_local_time()))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[StudentTree] 更新进度失败: {e}")
            return False

    @staticmethod
    def increase_hint_level(session_id: int, topic: str, question: str) -> int:
        """
        提高某个问题的提示强度

        参数：
            session_id: 会话 ID
            topic: 主题
            question: 问题

        返回：
            新的提示强度 (0-3)
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            c.execute("""
                SELECT hint_level FROM student_progress
                WHERE session_id = ? AND topic = ? AND question = ?
            """, (session_id, topic, question))

            row = c.fetchone()

            if row:
                current_level = row[0]
                new_level = min(current_level + 1, 3)  # 最大为 3

                c.execute("""
                    UPDATE student_progress
                    SET hint_level = ?, last_updated = ?
                    WHERE session_id = ? AND topic = ? AND question = ?
                """, (new_level, get_local_time(), session_id, topic, question))

                conn.commit()
                conn.close()
                return new_level

            conn.close()
            return 0

        except Exception as e:
            print(f"[StudentTree] 提高提示强度失败: {e}")
            return 0

    @staticmethod
    def reset_progress(session_id: int) -> bool:
        """
        重置某个会话的学习进度

        参数：
            session_id: 会话 ID

        返回：
            是否重置成功
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            c.execute("DELETE FROM student_progress WHERE session_id = ?", (session_id,))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[StudentTree] 重置进度失败: {e}")
            return False


# 工具函数，供 LangChain Agent 调用
def get_student_progress(session_id: int) -> dict:
    """获取学生学习进度（供 Agent 调用）"""
    return StudentTree.get_progress(session_id)


def update_student_progress(
    session_id: int,
    topic: str,
    question: str,
    answered: bool = False,
    hint_level: int = 0
) -> str:
    """更新学生学习进度（供 Agent 调用）"""
    success = StudentTree.update_progress(session_id, topic, question, answered, hint_level)
    return "更新成功" if success else "更新失败"
