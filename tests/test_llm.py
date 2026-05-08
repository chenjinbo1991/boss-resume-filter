"""
测试 LLM 连接
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 50)
print("LLM 连接测试")
print("=" * 50)

# 读取配置
llm_type = os.getenv("LOCAL_LLM_TYPE", "openai").lower()
base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1")
model = os.getenv("LOCAL_LLM_MODEL", "qwen-plus")
api_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")

print(f"\n配置信息:")
print(f"  LLM 类型：{llm_type}")
print(f"  基础地址：{base_url}")
print(f"  模型名称：{model}")

# 测试连接
print(f"\n正在测试连接...")

try:
    if llm_type == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.1,
            max_tokens=256,
        )
    elif llm_type == "ollama":
        from langchain_community.llms import Ollama

        llm = Ollama(
            model=model,
            base_url=base_url.replace("/v1", ""),
            temperature=0.1,
        )
    else:
        print(f"❌ 不支持的 LLM 类型：{llm_type}")
        sys.exit(1)

    # 发送测试消息
    response = llm.invoke("你好，请用一句话介绍你自己")

    if hasattr(response, "content"):
        content = response.content
    elif hasattr(response, "text"):
        content = response.text
    else:
        content = str(response)

    print(f"\n✅ 连接成功!")
    print(f"\n模型回复:")
    print(f"  {content[:200]}")

except Exception as e:
    print(f"\n❌ 连接失败:")
    print(f"  错误信息：{e}")
    print(f"\n请检查:")
    print(f"  1. LLM 服务是否已启动")
    print(f"  2. base_url 是否正确")
    print(f"  3. API Key 是否正确")
    print(f"  4. 模型是否已下载/可用")

print("\n" + "=" * 50)
