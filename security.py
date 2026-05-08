"""
API Key 安全存储模块

使用操作系统级加密存储：
- Windows: DPAPI (Data Protection API)
- macOS: Keychain
- Linux: Secret Service / KWallet

API Key 按服务商统一存储，同一服务商的所有模型共享一个 API Key。
"""
import keyring

SERVICE_NAME = "boss-resume-filter"


def get_storage_key(provider: str) -> str:
    """
    生成用于 keyring 存储的键名（按服务商）

    Args:
        provider: 服务商名称（如 "qwen", "deepseek"）

    Returns:
        存储键名
    """
    return f"api_key:{provider}"


def save_api_key(provider: str, api_key: str) -> bool:
    """
    加密保存 API Key 到系统钥匙串

    Args:
        provider: 服务商名称（如 "qwen", "deepseek"）
        api_key: 要存储的 API Key

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(provider)
        keyring.set_password(SERVICE_NAME, key, api_key)
        return True
    except Exception as e:
        print(f"保存 API Key 失败：{e}")
        return False


def get_api_key(provider: str) -> str | None:
    """
    从系统钥匙串解密读取 API Key

    Args:
        provider: 服务商名称

    Returns:
        API Key，如果不存在或读取失败则返回 None
    """
    try:
        key = get_storage_key(provider)
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as e:
        print(f"读取 API Key 失败：{e}")
        return None


def delete_api_key(provider: str) -> bool:
    """
    从系统钥匙串删除 API Key

    Args:
        provider: 服务商名称

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(provider)
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception as e:
        print(f"删除 API Key 失败：{e}")
        return False


def list_all_providers() -> list[str]:
    """
    列出所有已配置 API Key 的服务商

    Returns:
        服务商列表
    """
    try:
        import keyring.backend
        backend = keyring.get_keyring()
        # 不同 backend 实现不同，这里尝试获取所有 key
        # Windows 没有直接列出所有 key 的方法，返回空列表
        return []
    except Exception:
        return []
