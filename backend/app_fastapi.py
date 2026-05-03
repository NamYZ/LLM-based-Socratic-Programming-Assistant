"""
使用 FastAPI 构建的后端服务 - 提供: 模型配置管理 - 对话会话管理 - 聊天接口 -- 入口层: app_fastapi.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from database import init_db, DB_PATH

# 导入 4 个路由模块
from routers.config_router import router as config_router
from routers.session_router import router as session_router
from routers.chat_router import router as chat_router
from routers.assembly_router import router as assembly_router

# 创建 FastAPI 应用
app = FastAPI()

# CORS配置（允许跨域访问, 确保前端无论以什么方式都能访问后端接口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(config_router, tags=["配置管理"])
app.include_router(session_router, tags=["会话管理"])
app.include_router(chat_router, tags=["聊天"])
app.include_router(assembly_router, tags=["Assembly Agent"])


@app.get("/")
async def index():
    """访问首页时返回一个简单的 JSON, 表明后端服务正在运行"""
    return {"message": "AI Coding Tool Backend API", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == '__main__':

    # 初始化数据库
    init_db()
    print(f"✅ 数据库路径: {DB_PATH}")

    # 启动后端服务 端口：5500
    uvicorn.run(app, host="0.0.0.0", port=5500)
    print("🚀 服务启动: http://localhost:5500")
