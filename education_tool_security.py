"""读取独立工具的加密内置 API Key。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from education_tool_config import EDUCATION_TOOL_SECRET_FILE

_WRAP_PARTS = (
    b"\x97\x1d\x83\xa6\x4f\xc2\x31\x78",
    b"\x2a\xe4\x59\x0b\xd1\x66\xbc\x35",
    b"\x70\xcf\x14\xea\x8d\x43\xf9\x22",
    b"\xb8\x05\x6e\xd7\x39\xa1\x4c\xf0",
)


def _resource_path(filename: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / filename


def _wrap_key() -> bytes:
    return hashlib.sha256(b"".join(_WRAP_PARTS)).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(map(len, blocks)) < length:
        blocks.append(
            hmac.new(
                key,
                nonce + counter.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    return b"".join(blocks)[:length]


def decrypt_embedded_secret(payload: dict[str, str]) -> str:
    """解密构建产物中的密钥载荷并校验完整性。"""
    try:
        nonce = base64.b64decode(payload["nonce"], validate=True)
        wrapped_key = base64.b64decode(payload["wrapped_key"], validate=True)
        ciphertext = base64.b64decode(payload["ciphertext"], validate=True)
        expected_tag = base64.b64decode(payload["tag"], validate=True)
    except (KeyError, ValueError) as error:
        raise RuntimeError("内置 API Key 数据格式无效") from error

    wrap_stream = _keystream(_wrap_key(), nonce, len(wrapped_key))
    data_key = bytes(a ^ b for a, b in zip(wrapped_key, wrap_stream))
    actual_tag = hmac.new(data_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_tag, expected_tag):
        raise RuntimeError("内置 API Key 完整性校验失败")

    plaintext = bytes(
        a ^ b for a, b in zip(ciphertext, _keystream(data_key, nonce, len(ciphertext)))
    )
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("内置 API Key 无法解密") from error


def get_embedded_api_key() -> str:
    """解密构建时嵌入的 API Key；源码调试可使用环境变量。"""
    environment_key = os.environ.get("EDUCATION_TOOL_API_KEY", "").strip()
    if environment_key:
        return environment_key

    secret_path = _resource_path(EDUCATION_TOOL_SECRET_FILE)
    if not secret_path.is_file():
        raise RuntimeError("当前程序未内置 API Key，请使用正式构建版本")

    try:
        payload = json.loads(secret_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("secret payload must be an object")
        return decrypt_embedded_secret(payload)
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("内置 API Key 无法解密") from error
