"""
API Key 迁移工具 - 将明文 API Key 迁移到系统钥匙串

运行此脚本将 api_config.json 中的明文 API Key 加密存储到系统钥匙串。
迁移后，明文 API Key 会被从配置文件中删除。
"""
import json
import sys
from pathlib import Path
from security import save_api_key, generate_service_id

# Windows PowerShell 编码兼容
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent
API_CONFIG_PATH = BASE_DIR / "api_config.json"


def migrate():
    if not API_CONFIG_PATH.exists():
        print("配置文件不存在")
        return

    with open(API_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)

    migrated = False
    saved_models = config.get("saved_models", [])

    print(f"发现 {len(saved_models)} 个已保存的模型")
    print()

    for model_config in saved_models:
        # 检查是否有明文 API Key
        if model_config.get("api_key"):
            api_key = model_config["api_key"]
            provider = model_config.get("api_provider", "unknown")
            model_name = model_config.get("model", "unknown")

            # 生成 service_id
            service_id = generate_service_id(provider, model_name)

            # 存储到 keyring
            print(f"迁移：{provider} / {model_name}")
            if save_api_key(service_id, api_key):
                # 删除明文，只保留引用
                model_config["api_key_ref"] = service_id
                del model_config["api_key"]
                migrated = True
                print(f"  [OK] 已加密存储到系统钥匙串")
            else:
                print(f"  [FAIL] 存储失败")
        elif model_config.get("api_key_ref"):
            provider = model_config.get("api_provider", "unknown")
            model_name = model_config.get("model", "unknown")
            print(f"跳过：{provider} / {model_name} (已加密)")

    # 处理当前模型的 API Key
    if config.get("api_key") and config.get("model") and config.get("api_provider"):
        provider = config.get("api_provider")
        model_name = config.get("model")
        api_key = config.get("api_key")
        service_id = generate_service_id(provider, model_name)

        print(f"\n迁移当前模型配置：{provider} / {model_name}")
        if save_api_key(service_id, api_key):
            config["api_key_ref"] = service_id
            # 保留 api_key 字段以兼容旧代码，但不再写入明文
            config["api_key"] = ""
            migrated = True
            print(f"  [OK] 已加密存储到系统钥匙串")

    # 保存迁移后的配置
    if migrated:
        with open(API_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print("\n[OK] 迁移完成！明文 API Key 已从配置文件中删除")
    else:
        print("\n[OK] 无需迁移，所有 API Key 已加密存储")


if __name__ == "__main__":
    migrate()
