# -*- coding: utf-8 -*-
"""AI-assisted enhancement for parsed job requirements.

The regex parser remains the source of the initial config. This module asks an
OpenAI-compatible chat model for a bounded patch and merges only validated
fields back into the one-job config.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from constants import USER_AGENT


AI_PARSE_TIMEOUT = (8, 45)
AI_PARSE_MAX_TOKENS = 1200
AI_PARSE_TEMPERATURE = 0.1

_EDU_VALUES = {"不限", "高中", "中专", "大专", "本科", "硕士", "博士"}
_NOISY_KEYWORD_RE = re.compile(
    r"^(?:API|Wind|Bloomberg|万得(?:API)?|彭博|数据库(?:技术)?|数据开发工具)$",
    re.IGNORECASE,
)
_SOFT_TRAIT_RE = re.compile(r"服务意识|团队精神|学习能力|执行能力|沟通能力|责任心|抗压能力|主动性|积极性")


@dataclass
class AIParseEnhancementResult:
    """Result of AI enhancement."""

    success: bool
    config: dict[str, Any]
    reason: str = ""
    model: str = ""
    warnings: list[str] | None = None


def enhance_config_with_ai(
    requirements_text: str,
    regex_config: dict[str, Any],
    api_config: dict[str, Any],
    api_key: str,
) -> AIParseEnhancementResult:
    """Enhance a regex-generated one-job config with an LLM patch.

    On any failure, returns success=False and the original regex_config copy.
    """
    base_config = copy.deepcopy(regex_config)
    if not requirements_text or not requirements_text.strip():
        return AIParseEnhancementResult(False, base_config, "需求文本为空")

    base_url = str(api_config.get("base_url", "")).rstrip("/")
    model = str(api_config.get("model", ""))
    if not base_url or not model or not api_key:
        return AIParseEnhancementResult(False, base_config, "AI 配置不完整")

    try:
        messages = _build_messages(requirements_text, base_config)
        content = _call_chat_completion(base_url, model, api_key, messages)
        patch = _parse_json_response(content)
        enhanced = _merge_patch(base_config, patch)
        warnings = [str(w).strip() for w in patch.get("warnings", []) if str(w).strip()]
        return AIParseEnhancementResult(True, enhanced, "AI 增强完成", model=model, warnings=warnings)
    except Exception as exc:
        return AIParseEnhancementResult(False, base_config, str(exc)[:120], model=model)


def _build_messages(requirements_text: str, regex_config: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是招聘需求结构化解析助手。你只能基于原文和正则初稿做补充、纠错、归一化。"
        "不要虚构原文没有的信息。返回严格 JSON 对象，不要 Markdown，不要解释。"
    )
    user = (
        "目标：在正则解析初稿基础上增强岗位配置。\n\n"
        "关键规则：\n"
        "1. '优先'、'加分'、'更佳'类条件进入 preferred_keywords_add，不进入 required_conditions_add。\n"
        "2. '必须'、'要求'、'具备'、'需要'类硬性条件才进入 required_conditions_add。\n"
        "3. 'A、B、C 等'、'A/B'、'A 或 B'、'至少一种'通常解析为 OR："
        "{\"type\":\"or\",\"items\":[\"A\",\"B\",\"C\"]}。\n"
        "4. 只有出现'同时'、'均需'、'全部'才解析为 AND。\n"
        "5. 学历最低门槛不要被'硕士优先'、'博士优先'覆盖。\n"
        "6. keywords 是核心技能匹配项，weight 只能 1-3；preferred_keywords 是优先加分项，bonus 只能 1-10。\n\n"
        "7. 万得/Wind、彭博/Bloomberg、API、数据库技术这类数据来源或泛化词不要加入 keywords。\n"
        "8. 服务意识、团队精神、学习能力、执行能力等软素质不要加入 required_conditions。\n\n"
        "返回 JSON schema：\n"
        "{\n"
        "  \"job_title\": \"可选，岗位名修正\",\n"
        "  \"basic_info\": {\"min_exp\": 可选整数, \"edu\": 可选枚举, \"max_age\": 可选整数或null,"
        " \"work_location\": 可选字符串, \"salary_min\": 可选整数或null, \"salary_max\": 可选整数或null},\n"
        "  \"keywords_add\": [{\"name\":\"技能\", \"weight\":1-3}],\n"
        "  \"keywords_update\": [{\"name\":\"已有技能\", \"weight\":1-3}],\n"
        "  \"preferred_keywords_add\": [{\"name\":\"优先项\", \"bonus\":1-10}],\n"
        "  \"required_conditions_add\": [\"字符串条件\", {\"type\":\"or|and\", \"items\":[\"项1\",\"项2\"], \"category\":\"可选\"}],\n"
        "  \"required_conditions_remove\": [\"要移除的字符串条件\"],\n"
        "  \"warnings\": [\"不确定或需要人工确认的点\"]\n"
        "}\n\n"
        "原始招聘需求：\n"
        f"{requirements_text}\n\n"
        "正则初稿 JSON：\n"
        f"{json.dumps(regex_config, ensure_ascii=False, indent=2)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _call_chat_completion(base_url: str, model: str, api_key: str, messages: list[dict[str, str]]) -> str:
    try:
        import certifi

        verify_path: str | bool = certifi.where()
    except ImportError:
        verify_path = True

    response = requests.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "max_tokens": AI_PARSE_MAX_TOKENS,
            "temperature": AI_PARSE_TEMPERATURE,
            "stream": False,
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": USER_AGENT,
            "Connection": "close",
        },
        timeout=AI_PARSE_TIMEOUT,
        verify=verify_path,
    )
    if response.status_code != 200:
        raise ValueError(f"AI HTTP {response.status_code}: {response.text[:160]}")

    data = response.json()
    return str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))


def _parse_json_response(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("AI 返回为空")
    cleaned = text.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if not match:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("AI 返回不是 JSON")
        data = json.loads(match.group(1) if match.lastindex else match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI JSON 顶层必须是对象")
    return data


def _merge_patch(regex_config: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(regex_config)
    jobs = config.get("job_requirements")
    if not isinstance(jobs, dict) or not jobs:
        raise ValueError("正则配置缺少 job_requirements")

    old_title = next(iter(jobs.keys()))
    job = copy.deepcopy(jobs[old_title])
    new_title = _clean_job_title(patch.get("job_title")) or _clean_job_title(old_title) or old_title

    basic = patch.get("basic_info", {})
    if isinstance(basic, dict):
        for key in ("min_exp", "max_age", "salary_min", "salary_max"):
            if key in basic:
                job[key] = _optional_int(basic.get(key), job.get(key))
        if "edu" in basic:
            edu = _clean_text(basic.get("edu"))
            if edu in _EDU_VALUES:
                job["edu"] = edu
        if "work_location" in basic:
            loc = _clean_text(basic.get("work_location"))
            job["work_location"] = loc or None

    job["keywords"] = _merge_weighted_items(
        job.get("keywords", []),
        patch.get("keywords_add", []),
        patch.get("keywords_update", []),
        value_key="weight",
        min_value=1,
        max_value=3,
    )
    job["preferred_keywords"] = _merge_weighted_items(
        job.get("preferred_keywords", []),
        patch.get("preferred_keywords_add", []),
        [],
        value_key="bonus",
        min_value=1,
        max_value=10,
    )
    job["required_conditions"] = _merge_required_conditions(
        job.get("required_conditions", []),
        patch.get("required_conditions_add", []),
        patch.get("required_conditions_remove", []),
    )

    config["job_requirements"] = {new_title: job}
    return config


def _merge_weighted_items(
    existing: Any,
    additions: Any,
    updates: Any,
    *,
    value_key: str,
    min_value: int,
    max_value: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    index: dict[str, int] = {}

    def add_or_update(raw: Any, default_value: int, allow_add: bool = True) -> None:
        if isinstance(raw, dict):
            name = _clean_text(raw.get("name"))
            raw_value = raw.get(value_key, raw.get("weight", raw.get("bonus", default_value)))
        else:
            name = _clean_text(raw)
            raw_value = default_value
        if not name:
            return
        if value_key == "weight" and _is_noisy_keyword(name):
            return
        value = _clamp_int(raw_value, default_value, min_value, max_value)
        key = re.sub(r"\s+", "", name).lower()
        if key in index:
            items[index[key]][value_key] = max(items[index[key]].get(value_key, min_value), value)
        elif allow_add:
            index[key] = len(items)
            items.append({"name": name, value_key: value})

    for raw in existing if isinstance(existing, list) else []:
        add_or_update(raw, 1)
    for raw in updates if isinstance(updates, list) else []:
        add_or_update(raw, 1, allow_add=False)
    for raw in additions if isinstance(additions, list) else []:
        add_or_update(raw, 1)
    return items


def _merge_required_conditions(existing: Any, additions: Any, removals: Any) -> list[Any]:
    conditions = list(existing) if isinstance(existing, list) else []
    remove_set = {_normalize_condition_key(item) for item in removals if _normalize_condition_key(item)} if isinstance(removals, list) else set()
    if remove_set:
        conditions = [cond for cond in conditions if _normalize_condition_key(cond) not in remove_set]

    seen = {_normalize_condition_key(cond) for cond in conditions}
    for raw in additions if isinstance(additions, list) else []:
        cond = _normalize_condition(raw)
        if _is_soft_trait_condition(cond):
            continue
        key = _normalize_condition_key(cond)
        if cond is not None and key and key not in seen:
            conditions.append(cond)
            seen.add(key)
    return conditions


def _normalize_condition(raw: Any) -> Any:
    if isinstance(raw, str):
        return _clean_text(raw) or None
    if not isinstance(raw, dict):
        return None
    cond_type = str(raw.get("type", "or")).lower()
    if cond_type not in {"or", "and"}:
        cond_type = "or"
    items = [_clean_text(item) for item in raw.get("items", []) if _clean_text(item)]
    if not items:
        return None
    result: dict[str, Any] = {"type": cond_type, "items": items}
    category = _clean_text(raw.get("category"))
    if category:
        result["category"] = category
    return result


def _normalize_condition_key(cond: Any) -> str:
    if isinstance(cond, str):
        return cond.strip().lower()
    if isinstance(cond, dict):
        cond_type = str(cond.get("type", "or")).lower()
        items = [_clean_text(item).lower() for item in cond.get("items", []) if _clean_text(item)]
        return f"{cond_type}:{','.join(items)}" if items else ""
    return ""


def _is_noisy_keyword(name: str) -> bool:
    compact = re.sub(r"\s+", "", name or "")
    return bool(_NOISY_KEYWORD_RE.match(compact))


def _is_soft_trait_condition(cond: Any) -> bool:
    if isinstance(cond, str):
        return bool(_SOFT_TRAIT_RE.search(cond))
    if isinstance(cond, dict):
        text = " ".join(_clean_text(item) for item in cond.get("items", []))
        category = _clean_text(cond.get("category"))
        return bool(_SOFT_TRAIT_RE.search(text + " " + category))
    return False


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_job_title(value: Any) -> str:
    title = _clean_text(value)
    title = re.sub(r"^(?:岗位|职位|招聘)\s*\d+\s*[：:、.\-]\s*", "", title)
    title = re.sub(r"^\d+\s*[：:、.\-]\s*", "", title)
    return title.strip()


def _optional_int(value: Any, fallback: Any) -> int | None:
    if value is None or value == "":
        return None
    return _clamp_int(value, fallback if fallback is not None else 0, 0, 1000)


def _clamp_int(value: Any, fallback: Any, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        try:
            parsed = int(fallback)
        except (TypeError, ValueError):
            parsed = min_value
    return max(min_value, min(max_value, parsed))
