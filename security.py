"""
API Key 安全存储模块

使用操作系统级加密存储：
- Windows: DPAPI (Data Protection API)
- macOS: Keychain
- Linux: Secret Service / KWallet

API Key 按服务商 + Base URL 组合存储，同一服务商不同接入方式（API / Token Plan）独立管理。
"""
from __future__ import annotations

import hashlib
import logging
import keyring

SERVICE_NAME = "boss-resume-filter"
logger = logging.getLogger(__name__)


def get_storage_key(provider: str, base_url: str | None = None) -> str:
    """
    生成用于 keyring 存储的键名（按服务商 + Base URL 组合）

    Args:
        provider: 服务商名称（如 "qwen", "deepseek"）
        base_url: API Base URL（可选，用于区分同一服务商的不同接入方式）

    Returns:
        存储键名
    """
    if base_url:
        # 用 base_url 的短 hash 区分不同接入方式；strip 尾部斜杠防止同一 URL 两种写法产生不同 key
        normalized = base_url.rstrip('/')
        url_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"api_key:{provider}:{url_hash}"
    return f"api_key:{provider}"


def save_api_key(provider: str, api_key: str, base_url: str | None = None) -> bool:
    """
    加密保存 API Key 到系统钥匙串

    Args:
        provider: 服务商名称（如 "qwen", "deepseek"）
        api_key: 要存储的 API Key
        base_url: API Base URL（可选，用于区分同一服务商的不同接入方式）

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(provider, base_url)
        keyring.set_password(SERVICE_NAME, key, api_key)
        return True
    except Exception as e:
        logger.warning("保存 API Key 失败：%s", e)
        return False


def get_api_key(provider: str, base_url: str | None = None) -> str | None:
    """
    从系统钥匙串解密读取 API Key

    Args:
        provider: 服务商名称
        base_url: API Base URL（可选，用于区分同一服务商的不同接入方式）

    Returns:
        API Key，如果不存在或读取失败则返回 None
    """
    try:
        # 优先用新格式（带 base_url）查找
        if base_url:
            key = get_storage_key(provider, base_url)
            result = keyring.get_password(SERVICE_NAME, key)
            if result:
                return result
        # 回退到旧格式（仅 provider）向后兼容
        key = get_storage_key(provider)
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as e:
        logger.warning("读取 API Key 失败：%s", e)
        return None


def delete_api_key(provider: str, base_url: str | None = None) -> bool:
    """
    从系统钥匙串删除 API Key（同时清理新旧两种格式，防止残留）

    Args:
        provider: 服务商名称
        base_url: API Base URL（可选，用于区分同一服务商的不同接入方式）

    Returns:
        是否成功
    """
    try:
        key = get_storage_key(provider, base_url)
        keyring.delete_password(SERVICE_NAME, key)
    except Exception as e:
        logger.warning("删除 API Key 失败：%s", e)
        return False
    # 同时清理另一种格式，防止孤儿 key 残留
    try:
        alt_key = get_storage_key(provider, None) if base_url else None
        if alt_key and alt_key != key:
            try:
                keyring.delete_password(SERVICE_NAME, alt_key)
            except Exception:
                pass  # 旧格式不存在，忽略
    except Exception:
        pass
    return True


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
