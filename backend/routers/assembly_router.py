"""
Assembly Agent Router
提供 Assembly Teaching Agent 的专用 API 端点
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import json
import tempfile
import os

from assembly_agent.state_manager import AgentStateManager
from assembly_agent.report_generator import LearningReportGenerator
from assembly_agent.error_tracker import ErrorTracker


router = APIRouter(prefix="/api/assembly", tags=["assembly"])

# 初始化管理器
state_manager = AgentStateManager()
report_generator = LearningReportGenerator()
error_tracker = ErrorTracker()


# ===== 请求模型 =====

class HintLevelRequest(BaseModel):
    """手动调整提示等级的请求"""
    session_id: int
    hint_level: int
    manual_mode: bool


class UserProfileRequest(BaseModel):
    """用户画像请求"""
    user_id: str = 'default_user'


# ===== API 端点 =====

@router.get("/progress/{session_id}")
async def get_progress(session_id: int):
    """
    获取当前任务进度

    返回:
        - current_step: 当前步骤索引
        - total_steps: 总步骤数
        - task_steps: 步骤列表
        - hint_level: 当前提示等级
        - manual_mode: 是否处于手动模式
        - completion_status: 完成状态
    """
    try:
        progress_info = state_manager.get_progress_info(session_id)
        return JSONResponse(content=progress_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")


@router.post("/hint-level")
async def set_hint_level(request: HintLevelRequest):
    """
    手动调整提示等级

    参数:
        - session_id: 会话ID
        - hint_level: 提示等级 (1-3)
        - manual_mode: 是否启用手动模式
    """
    try:
        # 设置手动模式
        state_manager.set_manual_hint_mode(request.session_id, request.manual_mode)

        # 如果启用手动模式，设置提示等级
        if request.manual_mode:
            success = state_manager.set_hint_level_manual(request.session_id, request.hint_level)
            if not success:
                raise HTTPException(status_code=400, detail="设置提示等级失败，请确保会话存在")

        return JSONResponse(content={
            "success": True,
            "session_id": request.session_id,
            "hint_level": request.hint_level,
            "manual_mode": request.manual_mode
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置提示等级失败: {str(e)}")


@router.get("/report/{session_id}")
async def generate_report(session_id: int, user_id: str = 'default_user'):
    """
    生成学习报告

    返回完整的学习报告 JSON，包含:
        - session_info: 会话信息
        - task_summary: 任务摘要
        - progress_timeline: 进度时间线
        - hint_usage_analysis: 提示使用分析
        - error_analysis: 错误分析
        - knowledge_points: 知识点列表
        - learning_metrics: 学习指标
        - recommendations: 学习建议
    """
    try:
        # 先尝试获取已生成的报告
        existing_report = report_generator.get_report(session_id)
        if existing_report:
            return JSONResponse(content=existing_report)

        # 生成新报告
        report = report_generator.generate_report(session_id, user_id)

        if 'error' in report:
            raise HTTPException(status_code=404, detail=report['error'])

        return JSONResponse(content=report)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


@router.get("/report/{session_id}/export")
async def export_report(session_id: int, format: str = "json", user_id: str = 'default_user'):
    """
    导出学习报告为文件

    参数:
        - session_id: 会话ID
        - format: 导出格式 (json, markdown)
        - user_id: 用户ID

    返回:
        可下载的文件
    """
    try:
        # 获取或生成报告
        report = report_generator.get_report(session_id)
        if not report:
            report = report_generator.generate_report(session_id, user_id)

        if 'error' in report:
            raise HTTPException(status_code=404, detail=report['error'])

        # 根据格式导出
        if format == "json":
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
                temp_path = f.name

            filename = f"learning_report_{session_id}.json"
            return FileResponse(
                path=temp_path,
                filename=filename,
                media_type="application/json",
                background=lambda: os.unlink(temp_path)  # 删除临时文件
            )

        elif format == "markdown":
            # 导出为 Markdown
            md_content = report_generator.export_report_markdown(report)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(md_content)
                temp_path = f.name

            filename = f"learning_report_{session_id}.md"
            return FileResponse(
                path=temp_path,
                filename=filename,
                media_type="text/markdown",
                background=lambda: os.unlink(temp_path)
            )

        else:
            raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出报告失败: {str(e)}")


@router.get("/error-bank")
async def get_error_bank(user_id: str = 'default_user'):
    """
    获取用户的错题库

    返回:
        错误列表，按出现次数降序排列
    """
    try:
        error_bank = error_tracker.get_error_bank(user_id)
        statistics = error_tracker.get_error_statistics(user_id)

        return JSONResponse(content={
            "errors": error_bank,
            "statistics": statistics
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取错题库失败: {str(e)}")


@router.get("/profile")
async def get_user_profile(user_id: str = 'default_user'):
    """
    获取用户学习画像

    返回:
        - total_sessions: 总学习次数
        - completed_tasks: 完成任务数
        - total_errors: 总错误数
        - avg_hint_level: 平均提示等级
        - strong_areas: 擅长领域
        - weak_areas: 薄弱环节
    """
    try:
        import sqlite3
        from database import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 获取用户画像
        cursor.execute("""
            SELECT total_sessions, completed_tasks, total_errors, avg_hint_level,
                   strong_areas, weak_areas, last_updated
            FROM user_profiles
            WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()

        if not row:
            # 创建默认画像
            cursor.execute("""
                INSERT INTO user_profiles (user_id, created_at, last_updated)
                VALUES (?, datetime('now'), datetime('now'))
            """, (user_id,))
            conn.commit()

            profile = {
                'user_id': user_id,
                'total_sessions': 0,
                'completed_tasks': 0,
                'total_errors': 0,
                'avg_hint_level': 1.0,
                'strong_areas': [],
                'weak_areas': [],
                'last_updated': None
            }
        else:
            profile = {
                'user_id': user_id,
                'total_sessions': row[0],
                'completed_tasks': row[1],
                'total_errors': row[2],
                'avg_hint_level': row[3],
                'strong_areas': json.loads(row[4]) if row[4] else [],
                'weak_areas': json.loads(row[5]) if row[5] else [],
                'last_updated': row[6]
            }

        # 获取错误统计
        error_stats = error_tracker.get_error_statistics(user_id)
        profile['error_statistics'] = error_stats

        conn.close()

        return JSONResponse(content=profile)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户画像失败: {str(e)}")


@router.post("/profile/update")
async def update_user_profile(user_id: str = 'default_user'):
    """
    更新用户画像（基于所有会话数据重新计算）
    """
    try:
        import sqlite3
        from database import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 统计总会话数
        cursor.execute("""
            SELECT COUNT(DISTINCT session_id)
            FROM assembly_agent_sessions
        """)
        total_sessions = cursor.fetchone()[0] or 0

        # 统计完成任务数
        cursor.execute("""
            SELECT COUNT(*)
            FROM assembly_agent_sessions
            WHERE completion_status = 'completed'
        """)
        completed_tasks = cursor.fetchone()[0] or 0

        # 计算平均提示等级
        cursor.execute("""
            SELECT AVG(hint_level)
            FROM assembly_agent_sessions
        """)
        avg_hint_level = cursor.fetchone()[0] or 1.0

        # 获取错误统计
        error_stats = error_tracker.get_error_statistics(user_id)
        total_errors = error_stats['total_errors']

        # 分析强弱领域（基于错误频率）
        weak_areas = [item['point'] for item in error_stats['top_weak_points']]

        # 更新或创建用户画像
        cursor.execute("""
            INSERT OR REPLACE INTO user_profiles
            (user_id, total_sessions, completed_tasks, total_errors, avg_hint_level,
             weak_areas, last_updated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'),
                    COALESCE((SELECT created_at FROM user_profiles WHERE user_id = ?), datetime('now')))
        """, (user_id, total_sessions, completed_tasks, total_errors, avg_hint_level,
              json.dumps(weak_areas, ensure_ascii=False), user_id))

        conn.commit()
        conn.close()

        return JSONResponse(content={
            "success": True,
            "message": "用户画像已更新"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新用户画像失败: {str(e)}")
