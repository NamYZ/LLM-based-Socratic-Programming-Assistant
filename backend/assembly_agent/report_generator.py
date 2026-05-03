"""
Learning Report Generator for Assembly Teaching Agent
生成综合学习报告，包含统计分析、进度时间线、错误分析、知识点评估
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from database import DB_PATH


class LearningReportGenerator:
    """学习报告生成器"""

    def __init__(self):
        self.db_path = DB_PATH

    def generate_report(self, session_id: int, user_id: str = 'default_user') -> Dict[str, Any]:
        """
        生成综合学习报告

        Args:
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            包含完整学习分析的报告字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. 获取会话基本信息
        session_info = self._get_session_info(cursor, session_id)
        if not session_info:
            conn.close()
            return {'error': '会话不存在'}

        # 2. 获取 agent 状态
        agent_state = self._get_agent_state(cursor, session_id)

        # 3. 获取消息历史
        messages = self._get_messages(cursor, session_id)

        # 4. 分析学习模式
        learning_analysis = self._analyze_learning_patterns(messages, agent_state)

        # 5. 生成报告
        report = {
            'session_id': session_id,
            'generated_at': datetime.now().isoformat(),
            'session_info': {
                'title': session_info['title'],
                'mode': session_info['mode'],
                'created_at': session_info['created_at'],
                'updated_at': session_info['updated_at'],
                'duration_minutes': self._calculate_duration(session_info),
                'message_count': len(messages)
            },
            'task_summary': self._generate_task_summary(agent_state),
            'progress_timeline': self._generate_timeline(messages, agent_state),
            'hint_usage_analysis': self._analyze_hint_usage(agent_state, messages),
            'error_analysis': self._analyze_errors(agent_state, cursor, user_id),
            'knowledge_points': self._extract_knowledge_points(messages, agent_state),
            'learning_metrics': learning_analysis,
            'recommendations': self._generate_recommendations(agent_state, learning_analysis)
        }

        # 6. 存储报告
        self._store_report(cursor, session_id, report)

        conn.commit()
        conn.close()

        return report

    def _get_session_info(self, cursor, session_id: int) -> Optional[Dict[str, Any]]:
        """获取会话基本信息"""
        cursor.execute("""
            SELECT id, title, mode, created_at, updated_at
            FROM sessions_vscode
            WHERE id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'id': row[0],
            'title': row[1],
            'mode': row[2],
            'created_at': row[3],
            'updated_at': row[4]
        }

    def _get_agent_state(self, cursor, session_id: int) -> Dict[str, Any]:
        """获取 agent 状态"""
        cursor.execute("""
            SELECT mode, task_steps, current_step, user_code, hint_level,
                   error_history, requirement, hint_level_manual_mode,
                   total_steps, completion_status
            FROM assembly_agent_sessions
            WHERE session_id = ?
        """, (session_id,))

        row = cursor.fetchone()
        if not row:
            return {}

        return {
            'mode': row[0],
            'task_steps': json.loads(row[1]) if row[1] else [],
            'current_step': row[2],
            'user_code': row[3],
            'hint_level': row[4],
            'error_history': json.loads(row[5]) if row[5] else [],
            'requirement': row[6],
            'manual_mode': row[7] == 1 if len(row) > 7 else False,
            'total_steps': row[8] if len(row) > 8 else 0,
            'completion_status': row[9] if len(row) > 9 else 'in_progress'
        }

    def _get_messages(self, cursor, session_id: int) -> List[Dict[str, Any]]:
        """获取消息历史"""
        cursor.execute("""
            SELECT role, content, created_at
            FROM messages_vscode
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, (session_id,))

        return [
            {'role': row[0], 'content': row[1], 'timestamp': row[2]}
            for row in cursor.fetchall()
        ]

    def _calculate_duration(self, session_info: Dict[str, Any]) -> float:
        """计算会话持续时间（分钟）"""
        try:
            created = datetime.fromisoformat(session_info['created_at'])
            updated = datetime.fromisoformat(session_info['updated_at'])
            duration = (updated - created).total_seconds() / 60
            return round(duration, 2)
        except:
            return 0.0

    def _generate_task_summary(self, agent_state: Dict[str, Any]) -> Dict[str, Any]:
        """生成任务摘要"""
        task_steps = agent_state.get('task_steps', [])
        current_step = agent_state.get('current_step', 0)
        total_steps = len(task_steps)

        return {
            'requirement': agent_state.get('requirement', ''),
            'total_steps': total_steps,
            'completed_steps': current_step,
            'completion_rate': round(current_step / total_steps * 100, 2) if total_steps > 0 else 0,
            'completion_status': agent_state.get('completion_status', 'in_progress'),
            'task_steps': task_steps,
            'current_step_index': current_step
        }

    def _generate_timeline(self, messages: List[Dict[str, Any]], agent_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成进度时间线"""
        timeline = []

        for i, msg in enumerate(messages):
            if msg['role'] == 'user':
                timeline.append({
                    'timestamp': msg['timestamp'],
                    'type': 'user_input',
                    'content': msg['content'][:100] + '...' if len(msg['content']) > 100 else msg['content']
                })
            elif msg['role'] == 'assistant':
                timeline.append({
                    'timestamp': msg['timestamp'],
                    'type': 'assistant_response',
                    'content': msg['content'][:100] + '...' if len(msg['content']) > 100 else msg['content']
                })

        return timeline

    def _analyze_hint_usage(self, agent_state: Dict[str, Any], messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析提示使用情况"""
        final_hint_level = agent_state.get('hint_level', 1)
        manual_mode = agent_state.get('manual_mode', False)

        # 统计提示升级次数（简化版，实际可以从消息中提取）
        hint_escalations = 0
        for msg in messages:
            if msg['role'] == 'assistant' and ('提示等级' in msg['content'] or 'hint' in msg['content'].lower()):
                hint_escalations += 1

        return {
            'final_hint_level': final_hint_level,
            'manual_mode_used': manual_mode,
            'hint_escalations': hint_escalations,
            'hint_level_description': self._get_hint_level_description(final_hint_level)
        }

    def _get_hint_level_description(self, level: int) -> str:
        """获取提示等级描述"""
        descriptions = {
            1: '引导式 - 方向性问题',
            2: '适中 - 概念性问题',
            3: '明显 - 细节性问题'
        }
        return descriptions.get(level, '未知')

    def _analyze_errors(self, agent_state: Dict[str, Any], cursor, user_id: str) -> Dict[str, Any]:
        """分析错误情况"""
        error_history = agent_state.get('error_history', [])

        # 按类型统计
        error_types = {}
        for error in error_history:
            error_type = error.get('type', 'unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1

        # 获取错题库中相关错误
        cursor.execute("""
            SELECT error_category, occurrence_count, knowledge_point
            FROM error_bank
            WHERE user_id = ?
            ORDER BY occurrence_count DESC
            LIMIT 5
        """, (user_id,))

        top_errors = [
            {
                'category': row[0],
                'count': row[1],
                'knowledge_point': row[2]
            }
            for row in cursor.fetchall()
        ]

        return {
            'total_errors': len(error_history),
            'error_by_type': error_types,
            'error_details': error_history,
            'top_recurring_errors': top_errors
        }

    def _extract_knowledge_points(self, messages: List[Dict[str, Any]], agent_state: Dict[str, Any]) -> List[str]:
        """提取涉及的知识点"""
        knowledge_points = set()

        # 从需求中提取
        requirement = agent_state.get('requirement', '')
        if '循环' in requirement or 'loop' in requirement.lower():
            knowledge_points.add('循环结构')
        if '寄存器' in requirement or 'register' in requirement.lower():
            knowledge_points.add('寄存器使用')
        if '内存' in requirement or 'memory' in requirement.lower():
            knowledge_points.add('内存操作')
        if '栈' in requirement or 'stack' in requirement.lower():
            knowledge_points.add('栈操作')
        if '条件' in requirement or 'condition' in requirement.lower():
            knowledge_points.add('条件判断')

        # 从错误历史中提取
        for error in agent_state.get('error_history', []):
            category = error.get('category', '')
            if category:
                knowledge_points.add(category)

        return list(knowledge_points)

    def _analyze_learning_patterns(self, messages: List[Dict[str, Any]], agent_state: Dict[str, Any]) -> Dict[str, Any]:
        """分析学习模式"""
        user_messages = [m for m in messages if m['role'] == 'user']
        assistant_messages = [m for m in messages if m['role'] == 'assistant']

        return {
            'interaction_count': len(messages),
            'user_message_count': len(user_messages),
            'assistant_message_count': len(assistant_messages),
            'avg_user_message_length': sum(len(m['content']) for m in user_messages) / len(user_messages) if user_messages else 0,
            'engagement_level': self._calculate_engagement(user_messages),
            'learning_pace': self._calculate_learning_pace(agent_state, messages)
        }

    def _calculate_engagement(self, user_messages: List[Dict[str, Any]]) -> str:
        """计算参与度"""
        if len(user_messages) < 3:
            return '低'
        elif len(user_messages) < 10:
            return '中'
        else:
            return '高'

    def _calculate_learning_pace(self, agent_state: Dict[str, Any], messages: List[Dict[str, Any]]) -> str:
        """计算学习节奏"""
        total_steps = len(agent_state.get('task_steps', []))
        current_step = agent_state.get('current_step', 0)
        message_count = len(messages)

        if total_steps == 0:
            return '未开始'

        messages_per_step = message_count / max(current_step, 1)

        if messages_per_step < 5:
            return '快速'
        elif messages_per_step < 10:
            return '适中'
        else:
            return '缓慢'

    def _generate_recommendations(self, agent_state: Dict[str, Any], learning_analysis: Dict[str, Any]) -> List[str]:
        """生成学习建议"""
        recommendations = []

        # 基于完成率
        completion_rate = agent_state.get('current_step', 0) / max(len(agent_state.get('task_steps', [])), 1)
        if completion_rate < 0.5:
            recommendations.append('建议继续完成当前任务，巩固基础知识')
        elif completion_rate >= 1.0:
            recommendations.append('恭喜完成任务！可以尝试更复杂的挑战')

        # 基于错误数量
        error_count = len(agent_state.get('error_history', []))
        if error_count > 5:
            recommendations.append('建议复习基础概念，特别关注错误频发的知识点')
        elif error_count == 0:
            recommendations.append('表现优秀！可以尝试独立完成类似任务')

        # 基于提示等级
        hint_level = agent_state.get('hint_level', 1)
        if hint_level >= 3:
            recommendations.append('建议加强基础练习，多做类似题目提升熟练度')

        # 基于学习节奏
        pace = learning_analysis.get('learning_pace', '适中')
        if pace == '缓慢':
            recommendations.append('学习节奏较慢，建议先理解核心概念再动手实践')

        return recommendations

    def _store_report(self, cursor, session_id: int, report: Dict[str, Any]):
        """存储报告到数据库"""
        cursor.execute("""
            INSERT INTO learning_reports (session_id, report_data, generated_at)
            VALUES (?, ?, ?)
        """, (session_id, json.dumps(report, ensure_ascii=False), datetime.now().isoformat()))

    def get_report(self, session_id: int) -> Optional[Dict[str, Any]]:
        """获取已生成的报告"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT report_data, generated_at
            FROM learning_reports
            WHERE session_id = ?
            ORDER BY generated_at DESC
            LIMIT 1
        """, (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return json.loads(row[0])

    def export_report_markdown(self, report: Dict[str, Any]) -> str:
        """导出报告为 Markdown 格式"""
        md = f"""# 学习报告

## 会话信息
- **标题**: {report['session_info']['title']}
- **模式**: {report['session_info']['mode']}
- **持续时间**: {report['session_info']['duration_minutes']} 分钟
- **消息数**: {report['session_info']['message_count']}

## 任务摘要
- **需求**: {report['task_summary']['requirement']}
- **总步骤数**: {report['task_summary']['total_steps']}
- **已完成步骤**: {report['task_summary']['completed_steps']}
- **完成率**: {report['task_summary']['completion_rate']}%
- **状态**: {report['task_summary']['completion_status']}

## 提示使用分析
- **最终提示等级**: {report['hint_usage_analysis']['final_hint_level']} ({report['hint_usage_analysis']['hint_level_description']})
- **手动模式**: {'是' if report['hint_usage_analysis']['manual_mode_used'] else '否'}
- **提示升级次数**: {report['hint_usage_analysis']['hint_escalations']}

## 错误分析
- **总错误数**: {report['error_analysis']['total_errors']}
- **错误类型分布**: {json.dumps(report['error_analysis']['error_by_type'], ensure_ascii=False)}

## 学习指标
- **互动次数**: {report['learning_metrics']['interaction_count']}
- **参与度**: {report['learning_metrics']['engagement_level']}
- **学习节奏**: {report['learning_metrics']['learning_pace']}

## 建议
"""
        for rec in report['recommendations']:
            md += f"- {rec}\n"

        md += f"\n---\n生成时间: {report['generated_at']}\n"

        return md
