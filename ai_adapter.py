"""Provider-aware AI API adapter and model capability cache."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from constants import USER_AGENT
from paths import BASE_DIR


CAPABILITY_CACHE_PATH = BASE_DIR / ".storage" / "model_capabilities.json"
DEFAULT_AZURE_API_VERSION = "2024-10-21"


def detect_protocol(api_config: dict) -> str:
    """Return the wire protocol required by the configured endpoint."""
    provider = str(api_config.get("api_provider") or "").lower()
    base_url = str(api_config.get("base_url") or "").lower()
    if provider == "anthropic" or "api.anthropic.com" in base_url:
        return "anthropic"
    if provider == "azure" or ".openai.azure.com" in base_url:
        return "azure"
    return "openai_compatible"


def capability_cache_key(api_config: dict) -> str:
    """Build a non-secret cache key scoped to endpoint and model."""
    return "|".join((
        detect_protocol(api_config),
        str(api_config.get("base_url") or "").rstrip("/").lower(),
        str(api_config.get("model") or "").strip().lower(),
    ))


def load_capability(api_config: dict) -> dict | None:
    """Load cached capability data, returning None for missing/corrupt cache."""
    try:
        data = json.loads(CAPABILITY_CACHE_PATH.read_text(encoding="utf-8"))
        value = data.get(capability_cache_key(api_config))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def save_capability(api_config: dict, capability: dict) -> None:
    """Atomically cache capability metadata without credentials or responses."""
    try:
        CAPABILITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(CAPABILITY_CACHE_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError, TypeError):
            data = {}
        clean = {
            "status": str(capability.get("status") or "unknown"),
            "protocol": str(capability.get("protocol") or detect_protocol(api_config)),
            "output_mode": str(capability.get("output_mode") or "json_text"),
            "message": str(capability.get("message") or "")[:200],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        data[capability_cache_key(api_config)] = clean
        temp_path = Path(f"{CAPABILITY_CACHE_PATH}.tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, CAPABILITY_CACHE_PATH)
    except OSError:
        return


def _append_query(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault(key, value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _azure_url(api_config: dict) -> str:
    base_url = str(api_config.get("base_url") or "").rstrip("/")
    if base_url.endswith("/chat/completions"):
        return _append_query(
            base_url,
            "api-version",
            str(api_config.get("api_version") or DEFAULT_AZURE_API_VERSION),
        )
    if "/openai/v1" in base_url:
        return f"{base_url}/chat/completions"
    deployment = str(api_config.get("deployment") or api_config.get("model") or "").strip()
    url = f"{base_url}/openai/deployments/{deployment}/chat/completions"
    return _append_query(
        url,
        "api-version",
        str(api_config.get("api_version") or DEFAULT_AZURE_API_VERSION),
    )


def build_request(
    api_config: dict,
    api_key: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    temperature: float,
    tool: dict | None = None,
    force_tool: bool = False,
) -> tuple[str, dict, dict, str]:
    """Build a provider-specific request with one normalized input shape."""
    protocol = detect_protocol(api_config)
    base_url = str(api_config.get("base_url") or "").rstrip("/")
    model = str(api_config.get("model") or "")
    if protocol == "anthropic":
        url = f"{base_url}/messages" if base_url.endswith("/v1") else f"{base_url}/v1/messages"
        system_parts = [str(m.get("content") or "") for m in messages if m.get("role") == "system"]
        body: dict[str, Any] = {
            "model": model,
            "messages": [m for m in messages if m.get("role") != "system"],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if tool:
            fn = tool["function"]
            body["tools"] = [{
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn["parameters"],
            }]
            if force_tool:
                body["tool_choice"] = {"type": "tool", "name": fn["name"]}
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": USER_AGENT,
            "Connection": "close",
        }
        return url, headers, body, protocol

    url = _azure_url(api_config) if protocol == "azure" else f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Connection": "close",
    }
    headers["api-key" if protocol == "azure" else "Authorization"] = (
        api_key if protocol == "azure" else f"Bearer {api_key}"
    )
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if tool:
        body["tools"] = [tool]
        if force_tool:
            body["tool_choice"] = {
                "type": "function",
                "function": {"name": tool["function"]["name"]},
            }
    base_lower = base_url.lower()
    model_lower = model.lower()
    if "dashscope.aliyuncs.com" in base_lower and model_lower.startswith("qwen3.7"):
        body["enable_thinking"] = False
    if api_config.get("_disable_thinking") and "xiaomimimo.com" in base_lower:
        body["max_completion_tokens"] = body.pop("max_tokens")
        body["thinking"] = {"type": "disabled"}
    return url, headers, body, protocol


def normalize_response(protocol: str, payload: dict) -> tuple[dict, str]:
    """Normalize OpenAI and Anthropic responses to an OpenAI-like message."""
    if protocol != "anthropic":
        choice = (payload.get("choices") or [{}])[0]
        message = dict(choice.get("message") or {})
        if not message.get("content") and message.get("reasoning_content"):
            message["content"] = message["reasoning_content"]
        return message, str(choice.get("finish_reason") or "unknown")

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for block in payload.get("content") or []:
        if block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "type": "function",
                "function": {
                    "name": str(block.get("name") or ""),
                    "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                },
            })
    return {
        "content": "\n".join(text_parts),
        "tool_calls": tool_calls,
    }, str(payload.get("stop_reason") or "unknown")


def friendly_http_error(status_code: int, payload_or_text: Any) -> str:
    """Convert common provider errors to concise user-facing diagnostics."""
    if isinstance(payload_or_text, dict):
        error = payload_or_text.get("error") or {}
        if isinstance(error, dict):
            text = str(error.get("message") or error.get("type") or "")
        else:
            text = str(error)
    else:
        text = str(payload_or_text or "")
    lowered = text.lower()
    if status_code in (401, 403):
        return "认证失败（API Key 无效、无权限或已过期）"
    if status_code == 404:
        return "模型或 API 地址不存在"
    if status_code == 429:
        return "请求受限或配额不足"
    if "not activated" in lowered:
        return "该服务商未开通此模型"
    if "quota" in lowered or "limit" in lowered:
        return "配额超限"
    return f"HTTP {status_code}" + (f"：{text[:120]}" if text else "")
