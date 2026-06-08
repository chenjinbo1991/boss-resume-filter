# -*- coding: utf-8 -*-
"""Unit tests for security.py — API Key 安全存储模块"""
import unittest
from unittest.mock import patch, MagicMock
import security


def test_get_storage_key_format_without_base_url():
    """无 base_url 时格式正确（向后兼容）"""
    assert security.get_storage_key("qwen") == "api_key:qwen"
    assert security.get_storage_key("deepseek") == "api_key:deepseek"
    assert security.get_storage_key("openai") == "api_key:openai"


def test_get_storage_key_format_with_base_url():
    """有 base_url 时格式包含 hash"""
    key1 = security.get_storage_key("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    key2 = security.get_storage_key("qwen", "https://token-plan.example.com/v1")
    # 同一服务商不同 base_url 应生成不同 key
    assert key1 != key2
    assert key1.startswith("api_key:qwen:")
    assert key2.startswith("api_key:qwen:")
    # 同一 provider + base_url 应生成相同 key
    key1_again = security.get_storage_key("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert key1 == key1_again


def test_service_name_is_set():
    """SERVICE_NAME 常量非空"""
    assert security.SERVICE_NAME == "boss-resume-filter"


@patch("security.keyring")
def test_save_api_key_success(mock_keyring):
    """正常保存返回 True（无 base_url）"""
    mock_keyring.set_password = MagicMock()
    result = security.save_api_key("qwen", "sk-test-123")
    assert result is True
    mock_keyring.set_password.assert_called_once_with(
        "boss-resume-filter", "api_key:qwen", "sk-test-123"
    )


@patch("security.keyring")
def test_save_api_key_with_base_url(mock_keyring):
    """带 base_url 保存"""
    mock_keyring.set_password = MagicMock()
    result = security.save_api_key("qwen", "sk-test-123", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert result is True
    # key 应包含 hash
    call_args = mock_keyring.set_password.call_args[0]
    assert call_args[1].startswith("api_key:qwen:")
    assert call_args[1] != "api_key:qwen"


@patch("security.keyring")
@patch("security.logger.warning")
def test_save_api_key_failure(mock_warning, mock_keyring):
    """keyring 异常时返回 False"""
    mock_keyring.set_password = MagicMock(side_effect=Exception("keyring error"))
    result = security.save_api_key("qwen", "sk-test")
    assert result is False
    mock_warning.assert_called_once()
    assert mock_warning.call_args[0][0] == "保存 API Key 失败：%s"
    assert str(mock_warning.call_args[0][1]) == "keyring error"


@patch("security.keyring")
def test_get_api_key_found(mock_keyring):
    """找到 Key 时返回值（无 base_url）"""
    mock_keyring.get_password = MagicMock(return_value="sk-found")
    result = security.get_api_key("qwen")
    assert result == "sk-found"
    # 无 base_url 时只查旧格式
    mock_keyring.get_password.assert_called_once_with(
        "boss-resume-filter", "api_key:qwen"
    )


@patch("security.keyring")
def test_get_api_key_with_base_url_found(mock_keyring):
    """带 base_url 找到 Key"""
    # 第一次调用（新格式）返回 key，第二次不会调用
    def side_effect(service, key):
        if key.startswith("api_key:qwen:"):
            return "sk-found-new"
        return None
    mock_keyring.get_password = MagicMock(side_effect=side_effect)
    result = security.get_api_key("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert result == "sk-found-new"


@patch("security.keyring")
def test_get_api_key_with_base_url_fallback(mock_keyring):
    """带 base_url 但新格式未找到时回退到旧格式"""
    def side_effect(service, key):
        if key.startswith("api_key:qwen:"):
            return None  # 新格式没找到
        if key == "api_key:qwen":
            return "sk-found-old"  # 旧格式找到了
        return None
    mock_keyring.get_password = MagicMock(side_effect=side_effect)
    result = security.get_api_key("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert result == "sk-found-old"


@patch("security.keyring")
def test_get_api_key_not_found(mock_keyring):
    """未找到 Key 时返回 None"""
    mock_keyring.get_password = MagicMock(return_value=None)
    result = security.get_api_key("unknown_provider")
    assert result is None


@patch("security.keyring")
@patch("security.logger.warning")
def test_get_api_key_exception(mock_warning, mock_keyring):
    """keyring 异常时返回 None"""
    mock_keyring.get_password = MagicMock(side_effect=Exception("keyring error"))
    result = security.get_api_key("qwen")
    assert result is None
    mock_warning.assert_called_once()
    assert mock_warning.call_args[0][0] == "读取 API Key 失败：%s"
    assert str(mock_warning.call_args[0][1]) == "keyring error"


@patch("security.keyring")
def test_delete_api_key_success(mock_keyring):
    """正常删除返回 True"""
    mock_keyring.delete_password = MagicMock()
    result = security.delete_api_key("qwen")
    assert result is True
    mock_keyring.delete_password.assert_called_once_with(
        "boss-resume-filter", "api_key:qwen"
    )


@patch("security.keyring")
def test_delete_api_key_with_base_url(mock_keyring):
    """带 base_url 删除"""
    mock_keyring.delete_password = MagicMock()
    result = security.delete_api_key("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert result is True
    call_args = mock_keyring.delete_password.call_args[0]
    assert call_args[1].startswith("api_key:qwen:")


@patch("security.keyring")
@patch("security.logger.warning")
def test_delete_api_key_failure(mock_warning, mock_keyring):
    """keyring 异常时返回 False"""
    mock_keyring.delete_password = MagicMock(side_effect=Exception("delete error"))
    result = security.delete_api_key("qwen")
    assert result is False
    mock_warning.assert_called_once()
    assert mock_warning.call_args[0][0] == "删除 API Key 失败：%s"
    assert str(mock_warning.call_args[0][1]) == "delete error"


def test_list_all_providers_returns_list():
    """list_all_providers 返回列表（Windows 上为空列表）"""
    result = security.list_all_providers()
    assert isinstance(result, list)
