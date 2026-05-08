# 简单测试脚本，逐步检查bossmaster.py的问题
import sys
import os

print("开始测试bossmaster.py导入...")

try:
    # 尝试导入必要的模块而不执行主函数
    import importlib.util

    # 加载bossmaster.py但不执行
    spec = importlib.util.spec_from_file_location("bossmaster", "./bossmaster.py")
    module = importlib.util.module_from_spec(spec)

    # 捕获导入过程中的错误
    try:
        spec.loader.exec_module(module)
        print("✓ 模块导入成功")
    except Exception as e:
        print(f"✗ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"✗ 导入错误: {e}")
    import traceback
    traceback.print_exc()

print("测试完成")