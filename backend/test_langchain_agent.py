"""
测试 LangChain Agent 是否正常工作
"""
import asyncio
import sys
import os

# 添加 backend 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assembly_agent import AssemblyTeachingAgent
from database import get_api_key


async def test_agent():
    """测试 Agent 基本功能"""
    print("=" * 60)
    print("测试 LangChain Agent")
    print("=" * 60)

    # 获取 API 配置
    api_key, model_name, provider, base_url = get_api_key()

    if not api_key:
        print("❌ 错误：未配置 API Key")
        print("请先在前端配置 API Key")
        return

    print(f"✅ API 配置已加载")
    print(f"   模型: {model_name}")
    print(f"   提供商: {provider}")
    print(f"   Base URL: {base_url}")
    print()

    # 创建 Agent 实例
    print("🤖 创建 Agent 实例...")
    agent = AssemblyTeachingAgent(api_key, model_name, base_url)
    print(f"✅ Agent 类型: {agent.__class__.__name__}")
    print()

    # 测试场景1: Assembly Guide 模式 - 需求引导
    print("-" * 60)
    print("测试场景1: Assembly Guide 模式 - 需求引导")
    print("-" * 60)

    test_session_id = 99999  # 使用一个测试会话ID
    test_message = "我想写一个程序计算1到10的和"
    test_mode = "requirement_guide"

    print(f"📝 用户消息: {test_message}")
    print(f"🎯 模式: {test_mode}")
    print()
    print("🔄 Agent 处理中...")
    print()

    try:
        full_response = ""
        async for chunk in agent.process_message(
            session_id=test_session_id,
            user_message=test_message,
            mode=test_mode,
            requirement=test_message
        ):
            chunk_type = chunk.get('type')
            content = chunk.get('content', '')

            if chunk_type == 'status':
                print(f"   {content}")
            elif chunk_type == 'content':
                full_response += content
                print(content, end='', flush=True)
            elif chunk_type == 'error':
                print(f"\n❌ 错误: {content}")
                return
            elif chunk_type == 'done':
                print("\n")
                break

        print()
        print("=" * 60)
        print("✅ 测试完成！")
        print("=" * 60)
        print()
        print("完整回复:")
        print(full_response)
        print()

        # 检查是否有 reasoning_content 错误
        if "reasoning_content" in full_response.lower():
            print("⚠️  警告: 回复中提到了 reasoning_content")
        else:
            print("✅ 没有 reasoning_content 相关错误")

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_agent())
