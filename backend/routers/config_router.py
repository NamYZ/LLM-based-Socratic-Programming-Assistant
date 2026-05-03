"""
模型配置管理路由：处理 AI 模型配置的增删改查和激活操作
"""

from fastapi import APIRouter, HTTPException
import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SettingsRequest, ConfigRequest
from database import DB_PATH, get_api_key, get_local_time

router = APIRouter()

@router.get("/api/settings")
async def get_settings():
    """获取当前模型配置接口, 返回是否已配置以及部分配置信息(API Key 进行掩码处理)"""
    api_key, model_name, provider, base_url = get_api_key()
    if api_key:
        masked = api_key[:8] + '****' + api_key[-4:] if len(api_key) > 12 else '****'
        return {
            'api_key': masked,
            'model_name': model_name,
            'provider': provider or 'qwen',
            'base_url': base_url or '',
            'configured': True
        }
    return {'configured': False}


@router.post("/api/settings")
async def save_settings(req: SettingsRequest):
    """接收前端发送的模型配置数据，保存到数据库中"""
    if not req.api_key:
        raise HTTPException(status_code=400, detail='API Key 不能为空')
    if not req.base_url:
        raise HTTPException(status_code=400, detail='Base URL 不能为空')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查是否已有激活的配置
    c.execute("SELECT id, name FROM model_configs_vscode WHERE is_active = 1 LIMIT 1")
    active_config = c.fetchone()

    if active_config:
        # 更新现有的激活配置
        c.execute('''UPDATE model_configs_vscode
                     SET api_key = ?, model_name = ?, provider = ?, base_url = ?, updated_at = ?
                     WHERE id = ?''',
                  (req.api_key, req.model_name, req.provider, req.base_url, get_local_time(), active_config[0]))
    else:
        # 创建新的默认配置并激活
        local_time = get_local_time()
        c.execute('''INSERT INTO model_configs_vscode (name, provider, base_url, api_key, model_name, is_active, created_at, updated_at)
                     VALUES (?, ?, ?, ?, ?, 1, ?, ?)''',
                  ('默认配置', req.provider, req.base_url, req.api_key, req.model_name, local_time, local_time))

    conn.commit()
    conn.close()
    return {'success': True}


@router.get("/api/configs")
async def list_configs():
    """获取所有保存的 AI 模型配置列表，并且把 API Key 打码后返回给前端"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, name, provider, base_url, api_key, model_name, is_active, created_at
                 FROM model_configs_vscode ORDER BY created_at DESC''')
    rows = c.fetchall()
    conn.close()

    configs = []
    for r in rows:
        masked_key = r[4][:8] + '****' + r[4][-4:] if len(r[4]) > 12 else '****'
        configs.append({
            'id': r[0],
            'name': r[1],
            'provider': r[2],
            'base_url': r[3],
            'api_key': masked_key,
            'model_name': r[5],
            'is_active': r[6] == 1,
            'created_at': r[7]
        })
    return {'configs': configs}


@router.get("/api/configs/{config_id}")
async def get_config_detail(config_id: int):
    """获取单个配置详情，返回可编辑的完整字段"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, name, provider, base_url, api_key, model_name, is_active, created_at
                 FROM model_configs_vscode WHERE id = ?''', (config_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail='配置不存在')

    return {
        'config': {
            'id': row[0],
            'name': row[1],
            'provider': row[2],
            'base_url': row[3],
            'api_key': row[4],
            'model_name': row[5],
            'is_active': row[6] == 1,
            'created_at': row[7]
        }
    }


@router.post("/api/configs")
async def add_config(req: ConfigRequest):
    """添加新的模型配置"""
    if not req.name:
        raise HTTPException(status_code=400, detail='配置名称不能为空')
    if not req.api_key:
        raise HTTPException(status_code=400, detail='API Key 不能为空')
    if not req.base_url:
        raise HTTPException(status_code=400, detail='Base URL 不能为空')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查名称是否已存在
    c.execute("SELECT id FROM model_configs_vscode WHERE name = ?", (req.name,))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail='配置名称已存在')

    # 如果需要立即激活，先取消其他配置的激活状态
    if req.set_active:
        c.execute("UPDATE model_configs_vscode SET is_active = 0")

    local_time = get_local_time()
    c.execute('''INSERT INTO model_configs_vscode (name, provider, base_url, api_key, model_name, is_active, created_at, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (req.name, req.provider, req.base_url, req.api_key, req.model_name, 1 if req.set_active else 0, local_time, local_time))

    config_id = c.lastrowid
    conn.commit()
    conn.close()

    return {'success': True, 'id': config_id}


@router.put("/api/configs/{config_id}")
async def update_config(config_id: int, req: ConfigRequest):
    """更新指定的模型配置"""
    if not req.name:
        raise HTTPException(status_code=400, detail='配置名称不能为空')
    if not req.api_key:
        raise HTTPException(status_code=400, detail='API Key 不能为空')
    if not req.base_url:
        raise HTTPException(status_code=400, detail='Base URL 不能为空')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT is_active FROM model_configs_vscode WHERE id = ?", (config_id,))
    existing = c.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail='配置不存在')

    c.execute("SELECT id FROM model_configs_vscode WHERE name = ? AND id != ?", (req.name, config_id))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail='配置名称已存在')

    existing_is_active = existing[0] == 1
    target_is_active = 1 if (req.set_active or existing_is_active) else 0

    if req.set_active:
        c.execute("UPDATE model_configs_vscode SET is_active = 0")

    c.execute('''UPDATE model_configs_vscode
                 SET name = ?, provider = ?, base_url = ?, api_key = ?, model_name = ?, is_active = ?, updated_at = ?
                 WHERE id = ?''',
              (req.name, req.provider, req.base_url, req.api_key, req.model_name, target_is_active, get_local_time(), config_id))

    conn.commit()
    conn.close()

    return {'success': True, 'id': config_id, 'is_active': target_is_active == 1}


@router.delete("/api/configs/{config_id}")
async def delete_config(config_id: int):
    """删除模型配置"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查是否是激活的配置
    c.execute("SELECT is_active FROM model_configs_vscode WHERE id = ?", (config_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail='配置不存在')

    if row[0] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail='不能删除当前激活的配置')

    c.execute("DELETE FROM model_configs_vscode WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()

    return {'success': True}


@router.post("/api/configs/{config_id}/activate")
async def activate_config(config_id: int):
    """激活指定的模型配置"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 检查配置是否存在
    c.execute("SELECT id FROM model_configs_vscode WHERE id = ?", (config_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail='配置不存在')

    # 取消所有配置的激活状态
    c.execute("UPDATE model_configs_vscode SET is_active = 0")

    # 激活指定配置
    c.execute("UPDATE model_configs_vscode SET is_active = 1, updated_at = ? WHERE id = ?", (get_local_time(), config_id))

    conn.commit()
    conn.close()

    return {'success': True}
