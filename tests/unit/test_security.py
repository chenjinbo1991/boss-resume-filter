# -*- coding: utf-8 -*-
"""Unit tests for security.py — API Key 安全存储模块"""
import unittest
from unittest.mock import patch, MagicMock
import security


def test_get_storage_key_format():
    """存储键名格式正确"""
    assert security.get_storage_key("qwen") == "api_key:qwen"
    assert security.get_storage_key("deepseek") == "api_key:deepseek"
    assert security.get_storage_key("openai") == "api_key:openai"


def test_service_name_is_set():
    """SERVICE_NAME 常量非空"""
    assert security.SERVICE_NAME == "boss-resume-filter"


@patch("security.keyring")
def test_save_api_key_success(mock_keyring):
    """正常保存返回 True"""
    mock_keyring.set_password = MagicMock()
    result = security.save_api_key("qwen", "sk-test-123")
    assert result is True
    mock_keyring.set_password.assert_called_once_with(
        "boss-resume-filter", "api_key:qwen", "sk-test-123"
    )


@patch("security.keyring")
def test_save_api_key_failure(mock_keyring):
    """keyring 异常时返回 False"""
    mock_keyring.set_password = MagicMock(side_effect=Exception("keyring error"))
    result = security.save_api_key("qwen", "sk-test")
    assert result is False


@patch("security.keyring")
def test_get_api_key_found(mock_keyring):
    """找到 Key 时返回值"""
    mock_keyring.get_password = MagicMock(return_value="sk-found")
    result = security.get_api_key("qwen")
    assert result == "sk-found"
    mock_keyring.get_password.assert_called_once_with(
        "boss-resume-filter", "api_key:qwen"
    )


@patch("security.keyring")
def test_get_api_key_not_found(mock_keyring):
    """未找到 Key 时返回 None"""
    mock_keyring.get_password = MagicMock(return_value=None)
    result = security.get_api_key("unknown_provider")
    assert result is None


@patch("security.keyring")
def test_get_api_key_exception(mock_keyring):
    """keyring 异常时返回 None"""
    mock_keyring.get_password = MagicMock(side_effect=Exception("keyring error"))
    result = security.get_api_key("qwen")
    assert result is None


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
def test_delete_api_key_failure(mock_keyring):
    """keyring 异常时返回 False"""
    mock_keyring.delete_password = MagicMock(side_effect=Exception("delete error"))
    result = security.delete_api_key("qwen")
    assert result is False


def test_list_all_providers_returns_list():
    """list_all_providers 返回列表（Windows 上为空列表）"""
    result = security.list_all_providers()
    assert isinstance(result, list)
