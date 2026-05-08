"""
API Key 安全存储模块

使用操作系统级加密存储：
- Windows: DPAPI (Data Protection API)
- macOS: Keychain
- Linux: Secret Service / KWallet

API Key 加密后存储在系统钥匙串中，api_config.json 中只保存一个 service_id 引用。
即使配置文件泄露，攻击者也无法获取真实的 API Key。
"""
import keyring
import base64
import os

SERVICE_NAME = "boss-resume-filter"


def get_storage_key(service_id: str) -> str:
    """
    生成用于 keyring 存储的键名

    Args:
        service_id: 服务 ID（用于区分不同的 API 服务商配置）

    Returns:
        存储键名
    """
    return f"api_key:{service_id}"


def save_api_key(service_id: str, api_key: str) -> bool:
    """
    加密保存 API Key 到系统钥匙串

    Args:
        service_id: 服务 ID（如 "qwen_default", "deepseek_prod"）
        api_key: 要存储的 API Key

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(service_id)
        keyring.set_password(SERVICE_NAME, key, api_key)
        return True
    except Exception as e:
        print(f"保存 API Key 失败：{e}")
        return False


def get_api_key(service_id: str) -> str | None:
    """
    从系统钥匙串解密读取 API Key

    Args:
        service_id: 服务 ID

    Returns:
        API Key，如果不存在或读取失败则返回 None
    """
    try:
        key = get_storage_key(service_id)
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as e:
        print(f"读取 API Key 失败：{e}")
        return None


def delete_api_key(service_id: str) -> bool:
    """
    从系统钥匙串删除 API Key

    Args:
        service_id: 服务 ID

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(service_id)
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception as e:
        print(f"删除 API Key 失败：{e}")
        return False


def generate_service_id(provider: str, model_name: str) -> str:
    """
    生成唯一的服务 ID（用于 keyring 存储）

    Args:
        provider: 服务商名称（如 "qwen", "deepseek"）
        model_name: 模型名称

    Returns:
        唯一的服务 ID（Base64 编码，避免特殊字符）
    """
    raw = f"{provider}:{model_name}"
    # 用 Base64 编码确保 ID 中无特殊字符，适合作为 keyring 键名
    return base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8').rstrip('=')
