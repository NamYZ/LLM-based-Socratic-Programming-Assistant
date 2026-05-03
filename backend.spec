# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置文件 - 用于打包 AI Coding Tool 后端

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 收集所有需要的数据文件和子模块
# 显式添加 Python 包目录，确保 __init__.py 和所有模块文件都被正确打包
datas = [
    ('backend/assembly_agent', 'assembly_agent'),
    ('backend/ask_prompts', 'ask_prompts'),
]

# 自动收集 assembly_agent 和 ask_prompts 的所有子模块
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'pydantic',
    'langchain',
    'langchain_openai',
    'langchain_core',
    'langchain_community',

    # Assembly Agent 模块及其所有子模块
    'assembly_agent',
    'assembly_agent.simple_agent',
    'assembly_agent.state_manager',
    'assembly_agent.error_tracker',
    'assembly_agent.filtered_llm',
    'assembly_agent.langchain_tools',
    'assembly_agent.report_generator',
    'assembly_agent.prompts',
    'assembly_agent.prompts.system_prompt',
    'assembly_agent.prompts.mode_prompts',
    'assembly_agent.prompts.tool_prompts',

    # Ask Prompts 模块
    'ask_prompts',
    'ask_prompts.question_mode_prompts',
    'ask_prompts.guided_mode_prompts',

    # LangChain 额外的子模块（显式添加以确保打包）
    'langchain_core.tools',
    'langchain_core.runnables',
    'langchain_core.runnables.history',
]

a = Analysis(
    ['backend/app_fastapi.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
