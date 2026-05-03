"""
Error Tracker for Assembly Teaching Agent
自动追踪和分类用户的错误模式，构建个人错题库
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from database import DB_PATH


class ErrorTracker:
    """错误追踪器 - 自动记录和分析用户错误"""

    def __init__(self):
        self.db_path = DB_PATH

    def track_error(self, session_id: int, error_info: Dict[str, Any], user_id: str = 'default_user'):
        """
        追踪错误并更新错题库

        Args:
            session_id: 会话ID
            error_info: 错误信息字典，包含 category, description, code 等
            user_id: 用户ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        error_category = error_info.get('category', 'unknown')
        error_description = error_info.get('description', '')
        related_code = error_info.get('code', '')
        knowledge_point = self._extract_knowledge_point(error_category, error_description)

        # 检查是否已存在相同类别的错误
        cursor.execute("""
            SELECT id, occurrence_count FROM error_bank
            WHERE user_id = ? AND error_category = ? AND knowledge_point = ?
        """, (user_id, error_category, knowledge_point))

        existing = cursor.fetchone()
        now = datetime.now().isoformat()

        if existing:
            # 更新现有错误记录
            error_id, count = existing
            cursor.execute("""
                UPDATE error_bank
                SET occurrence_count = ?,
                    last_seen = ?,
                    related_code = ?,
                    updated_at = ?
                WHERE id = ?
            """, (count + 1, now, related_code, now, error_id))
        else:
            # 创建新错误记录
            cursor.execute("""
                INSERT INTO error_bank
                (user_id, error_category, error_description, knowledge_point,
                 occurrence_count, first_seen, last_seen, related_code, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """, (user_id, error_category, error_description, knowledge_point,
                  now, now, related_code, now, now))

        conn.commit()

        # 更新用户画像
        self._update_user_profile(cursor, user_id, error_category, knowledge_point)

        conn.commit()
        conn.close()

    def _extract_knowledge_point(self, error_category: str, error_description: str) -> str:
        """从错误类别和描述中提取知识点"""
        # 简单的知识点映射
        knowledge_map = {
            'syntax': '语法规则',
            'logic': '程序逻辑',
            'semantic': '语义理解',
            'register': '寄存器使用',
            'addressing': '寻址方式',
            'instruction': '指令使用',
            'loop': '循环结构',
            'condition': '条件判断',
            'memory': '内存操作',
            'stack': '栈操作'
        }

        # 尝试从错误类别中匹配
        for key, value in knowledge_map.items():
            if key in error_category.lower() or key in error_description.lower():
                return value

        return error_category

    def _update_user_profile(self, cursor, user_id: str, error_category: str, knowledge_point: str):
        """更新用户画像的薄弱环节"""
        # 获取或创建用户画像
        cursor.execute("SELECT weak_areas FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        now = datetime.now().isoformat()

        if row:
            weak_areas = json.loads(row[0]) if row[0] else []

            # 更新薄弱环节
            if knowledge_point not in weak_areas:
                weak_areas.append(knowledge_point)

            cursor.execute("""
                UPDATE user_profiles
                SET weak_areas = ?,
                    total_errors = total_errors + 1,
                    last_updated = ?
                WHERE user_id = ?
            """, (json.dumps(weak_areas, ensure_ascii=False), now, user_id))
        else:
            # 创建新的用户画像
            weak_areas = [knowledge_point]
            cursor.execute("""
                INSERT INTO user_profiles
                (user_id, total_errors, weak_areas, last_updated, created_at)
                VALUES (?, 1, ?, ?, ?)
            """, (user_id, json.dumps(weak_areas, ensure_ascii=False), now, now))

    def get_error_bank(self, user_id: str = 'default_user') -> List[Dict[str, Any]]:
        """获取用户的错题库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, error_category, error_description, knowledge_point,
                   occurrence_count, first_seen, last_seen, resolution_status
            FROM error_bank
            WHERE user_id = ?
            ORDER BY occurrence_count DESC, last_seen DESC
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'category': row[1],
                'description': row[2],
                'knowledge_point': row[3],
                'count': row[4],
                'first_seen': row[5],
                'last_seen': row[6],
                'status': row[7]
            }
            for row in rows
        ]

    def mark_error_resolved(self, error_id: int):
        """标记错误已解决"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE error_bank
            SET resolution_status = 'resolved',
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), error_id))

        conn.commit()
        conn.close()

    def get_error_statistics(self, user_id: str = 'default_user') -> Dict[str, Any]:
        """获取错误统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总错误数
        cursor.execute("""
            SELECT SUM(occurrence_count) FROM error_bank WHERE user_id = ?
        """, (user_id,))
        total_errors = cursor.fetchone()[0] or 0

        # 按类别统计
        cursor.execute("""
            SELECT error_category, SUM(occurrence_count) as count
            FROM error_bank
            WHERE user_id = ?
            GROUP BY error_category
            ORDER BY count DESC
        """, (user_id,))
        category_stats = [{'category': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # 按知识点统计
        cursor.execute("""
            SELECT knowledge_point, SUM(occurrence_count) as count
            FROM error_bank
            WHERE user_id = ?
            GROUP BY knowledge_point
            ORDER BY count DESC
            LIMIT 5
        """, (user_id,))
        knowledge_stats = [{'point': row[0], 'count': row[1]} for row in cursor.fetchall()]

        conn.close()

        return {
            'total_errors': total_errors,
            'by_category': category_stats,
            'top_weak_points': knowledge_stats
        }
