# -*- coding: utf-8 -*-
"""LLM-based candidate evaluation for BOSS resume screening."""
import json
import re
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional
from constants import SCORE_THRESHOLD_PASS, SCORE_THRESHOLD_RECOMMEND, SCORE_THRESHOLD_STRONG, USER_AGENT

import requests


@dataclass
class LLMEvalResult:
    """Result of a single LLM evaluation call."""
    success: bool
    adjustment: int = 0       # -10 ~ +10
    reason: str = ""          # ≤50 chars
    model: str = ""


_SYSTEM_PROMPT = (
    "你是一个资深技术招聘助手。根据岗位需求评估候选人的匹配程度。\n"
    "返回严格的 JSON 对象（不要包含其他文字）：\n"
    '{"adjustment": 整数(-10到+10), "reason": "50字以内评估理由"}\n'
    "评分标准：\n"
    "+8~+10: 高度匹配，有明显优势\n"
    "+3~+7: 较为匹配，有加分项\n"
    "0: 基本匹配，无特别加减分\n"
    "-1~-5: 存在不匹配之处\n"
    "-6~-10: 明显不匹配"
)

_USER_TEMPLATE = (
    "## 岗位需求\n{job_requirement}\n\n"
    "## 候选人信息\n{candidate_summary}\n\n"
    "请评估匹配度，返回 JSON。"
)


def _build_prompt(job_requirement: str, candidate_summary: str) -> list:
    """Build chat messages for LLM evaluation."""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(
            job_requirement=job_requirement,
            candidate_summary=candidate_summary,
        )},
    ]


def _parse_response(text: str) -> dict:
    """Parse LLM response text into {adjustment, reason} dict.

    Handles: plain JSON, markdown code blocks, Chinese punctuation.
    Clamps adjustment to [-10, +10].
    Raises ValueError if unparseable.
    """
    if not text or not text.strip():
        raise ValueError("Empty response")

    cleaned = text.strip()

    # Try direct JSON parse
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        # Try extracting from markdown code block: ```json ... ``` or ``` ... ```
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            # Try extracting first JSON object
            m = re.search(r'\{[^{}]*"adjustment"[^{}]*\}', cleaned, re.DOTALL)
            if m:
                # Normalize Chinese punctuation in JSON
                raw = m.group(0)
                raw = raw.replace('：', ':').replace('，', ',').replace('"', '"').replace('"', '"')
                data = json.loads(raw)
            else:
                raise ValueError(f"Cannot extract JSON from: {cleaned[:100]}")

    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data).__name__}")

    # Extract and validate adjustment
    adjustment = data.get('adjustment', 0)
    if not isinstance(adjustment, (int, float)):
        try:
            adjustment = int(adjustment)
        except (TypeError, ValueError):
            adjustment = 0
    adjustment = int(adjustment)
    # Clamp to [-10, +10]
    adjustment = max(-10, min(10, adjustment))

    # Extract and validate reason
    reason = str(data.get('reason', '')).strip()
    if len(reason) > 100:
        reason = reason[:100]

    return {'adjustment': adjustment, 'reason': reason}


def _call_llm_api(messages: list, api_config: dict, api_key: str) -> LLMEvalResult:
    """Call LLM API and return evaluation result.

    Uses the OpenAI-compatible /chat/completions endpoint.
    Retries on 429 (exponential backoff) and transient errors.
    """
    try:
        import certifi
        verify_path = certifi.where()
    except ImportError:
        verify_path = True

    base_url = api_config.get('base_url', '').rstrip('/')
    model = api_config.get('model', '')

    if not base_url or not model:
        return LLMEvalResult(success=False, reason="API config incomplete")

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Connection": "close",
    }
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 256,
        "temperature": 0.3,
        "stream": False,
    }
    timeout = (8, 30)

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            session = requests.Session()
            try:
                response = session.post(
                    url, json=body, headers=headers,
                    timeout=timeout, verify=verify_path,
                )
            finally:
                session.close()

            if response.status_code == 200:
                resp_data = response.json()
                content = (resp_data.get('choices', [{}])[0]
                           .get('message', {})
                           .get('content', ''))
                parsed = _parse_response(content)
                return LLMEvalResult(
                    success=True,
                    adjustment=parsed['adjustment'],
                    reason=parsed['reason'],
                    model=model,
                )
            elif response.status_code == 429:
                # Rate limited — exponential backoff
                delay = (2 ** attempt) + random.uniform(0, 0.5)
                print(f"  ⚠️ API 限流 (429)，{delay:.1f}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(delay)
                last_error = "Rate limited (429)"
                continue
            elif 500 <= response.status_code < 600:
                # Server error — retry with delay
                delay = 1 + random.uniform(0, 0.5)
                print(f"  ⚠️ API 服务端错误 ({response.status_code})，{delay:.1f}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(delay)
                last_error = f"Server error ({response.status_code})"
                continue
            else:
                # Client error — don't retry
                print(f"  ❌ API 请求失败 ({response.status_code}): {response.text[:200]}")
                return LLMEvalResult(success=False, reason=f"HTTP {response.status_code}")

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            delay = 1 + random.uniform(0, 0.5)
            print(f"  ⚠️ 网络异常：{type(e).__name__}，{delay:.1f}s 后重试 ({attempt+1}/{max_retries})")
            time.sleep(delay)
            last_error = str(e)
            continue
        except Exception as e:
            print(f"  ❌ LLM 调用异常：{type(e).__name__}: {e}")
            return LLMEvalResult(success=False, reason=str(e)[:50])

    return LLMEvalResult(success=False, reason=f"Max retries: {last_error}")


def _recalc_recommend_level(score: int) -> str:
    """Recalculate recommend level from adjusted score."""
    if score >= SCORE_THRESHOLD_STRONG:
        return "强烈推荐"
    elif score >= SCORE_THRESHOLD_RECOMMEND:
        return "推荐"
    return "待定"


def _evaluate_single(index: int, candidate: dict, job_requirement: str,
                     api_config: dict, api_key: str) -> tuple:
    """Evaluate a single candidate with LLM. Returns (index, result, candidate_ref)."""
    messages = _build_prompt(job_requirement, candidate.get('summary', ''))
    result = _call_llm_api(messages, api_config, api_key)

    # Rate limiting delay between calls
    delay = 1.0 + random.uniform(0, 0.5)
    time.sleep(delay)

    return index, result, candidate


def evaluate_batch(
    candidates: list,
    job_requirement: str,
    api_config: dict,
    api_key: str,
    *,
    max_candidates: int = 50,
    progress_callback=None,
    stop_event: Optional[threading.Event] = None,
    max_workers: int = 3,
) -> list:
    """Evaluate candidates with LLM and adjust scores (concurrent).

    Args:
        candidates: list of candidate_record dicts (passed filter, score >= SCORE_THRESHOLD_PASS)
        job_requirement: raw job requirement text
        api_config: dict with 'base_url' and 'model'
        api_key: API key string
        max_candidates: max number of candidates to evaluate
        progress_callback: callable(percentage, description)
        stop_event: threading.Event for cancellation
        max_workers: number of concurrent API calls (default 3)

    Returns:
        Updated candidates list (same objects, modified in-place).
    """
    if not candidates:
        return candidates

    # Take top N by score (most impactful to evaluate)
    to_evaluate = candidates[:max_candidates]
    total = len(to_evaluate)

    print(f"开始 AI 评估：{total} 人（共 {len(candidates)} 人通过筛选），并发数：{max_workers}")

    completed_count = 0
    count_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {}
        for i, candidate in enumerate(to_evaluate):
            if stop_event and stop_event.is_set():
                print("  [停止] 用户请求停止，跳过剩余 AI 评估")
                break
            future = executor.submit(
                _evaluate_single, i, candidate, job_requirement, api_config, api_key
            )
            future_to_index[future] = i

        # Collect results as they complete
        for future in as_completed(future_to_index):
            if stop_event and stop_event.is_set():
                # Cancel remaining futures
                for f in future_to_index:
                    f.cancel()
                print("  [停止] 用户请求停止，取消剩余 AI 评估")
                break

            try:
                idx, result, candidate = future.result()
                name = candidate.get('name', '?')
                rule_score = candidate.get('match_score', 0)

                if result.success:
                    # Store original score
                    candidate['rule_score'] = rule_score

                    # Apply adjustment and clamp
                    new_score = max(0, min(100, rule_score + result.adjustment))
                    candidate['match_score'] = new_score
                    candidate['recommend_level'] = _recalc_recommend_level(new_score)

                    # Store LLM metadata
                    candidate['llm_evaluated'] = True
                    candidate['llm_adjustment'] = result.adjustment
                    candidate['llm_reason'] = result.reason
                    candidate['llm_model'] = result.model

                    sign = "+" if result.adjustment > 0 else ""
                    print(f"  [{idx+1}/{total}] {name}: {rule_score} → {new_score} ({sign}{result.adjustment}) {result.reason}")
                else:
                    candidate['llm_evaluated'] = False
                    print(f"  [{idx+1}/{total}] {name}: 评估失败 ({result.reason})，保留原始分数 {rule_score}")

                # Update progress (thread-safe)
                with count_lock:
                    completed_count += 1
                    current = completed_count

                # Progress callback
                if progress_callback:
                    pct = int(current / total * 100)
                    progress_callback(pct, f"AI 评估中... {current}/{total}")

            except Exception as e:
                print(f"  [错误] AI 评估异常: {e}")

    return candidates
