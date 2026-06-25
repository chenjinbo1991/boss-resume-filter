"""Unit tests for provider-aware AI request adaptation."""
import json

from ai_adapter import build_request, detect_protocol, normalize_response


TOOL = {
    "type": "function",
    "function": {
        "name": "submit",
        "description": "submit result",
        "parameters": {"type": "object", "properties": {"value": {"type": "integer"}}},
    },
}
MESSAGES = [
    {"role": "system", "content": "system rule"},
    {"role": "user", "content": "evaluate"},
]


def test_detect_protocols():
    assert detect_protocol({"api_provider": "anthropic"}) == "anthropic"
    assert detect_protocol({"base_url": "https://x.openai.azure.com"}) == "azure"
    assert detect_protocol({"api_provider": "deepseek"}) == "openai_compatible"


def test_build_openai_compatible_request():
    url, headers, body, protocol = build_request(
        {"base_url": "https://api.example.com/v1", "model": "model-a"},
        "secret",
        MESSAGES,
        max_tokens=100,
        temperature=0,
        tool=TOOL,
        force_tool=True,
    )
    assert protocol == "openai_compatible"
    assert url == "https://api.example.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret"
    assert body["tool_choice"]["function"]["name"] == "submit"


def test_build_xiaomi_vision_request_disables_thinking():
    _url, _headers, body, protocol = build_request(
        {
            "api_provider": "xiaomi",
            "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
            "model": "mimo-v2.5",
            "_disable_thinking": True,
        },
        "secret",
        [{"role": "user", "content": "test"}],
        max_tokens=500,
        temperature=0,
    )

    assert protocol == "openai_compatible"
    assert "max_tokens" not in body
    assert body["max_completion_tokens"] == 500
    assert body["thinking"] == {"type": "disabled"}


def test_build_anthropic_request_converts_system_and_tool():
    url, headers, body, protocol = build_request(
        {"api_provider": "anthropic", "base_url": "https://api.anthropic.com/v1", "model": "claude-test"},
        "secret",
        MESSAGES,
        max_tokens=100,
        temperature=0,
        tool=TOOL,
        force_tool=True,
    )
    assert protocol == "anthropic"
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "secret"
    assert body["system"] == "system rule"
    assert body["messages"] == [{"role": "user", "content": "evaluate"}]
    assert body["tools"][0]["input_schema"]["type"] == "object"
    assert body["tool_choice"] == {"type": "tool", "name": "submit"}


def test_build_azure_legacy_request():
    url, headers, body, protocol = build_request(
        {
            "api_provider": "azure",
            "base_url": "https://resource.openai.azure.com",
            "model": "deployment-a",
        },
        "secret",
        MESSAGES,
        max_tokens=100,
        temperature=0,
    )
    assert protocol == "azure"
    assert "/openai/deployments/deployment-a/chat/completions" in url
    assert "api-version=" in url
    assert headers["api-key"] == "secret"
    assert body["model"] == "deployment-a"


def test_normalize_anthropic_tool_response():
    message, finish_reason = normalize_response("anthropic", {
        "content": [
            {"type": "text", "text": "done"},
            {"type": "tool_use", "name": "submit", "input": {"value": 1}},
        ],
        "stop_reason": "tool_use",
    })
    assert message["content"] == "done"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {"value": 1}
    assert finish_reason == "tool_use"


def test_normalize_reasoning_content_fallback():
    message, _ = normalize_response("openai_compatible", {
        "choices": [{"message": {"content": "", "reasoning_content": '{"value": 1}'}}],
    })
    assert message["content"] == '{"value": 1}'
