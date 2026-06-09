"""Unit tests for llm_eval module — mocked HTTP, no real API calls."""
import contextlib
import io
import json
import threading
from unittest.mock import patch, MagicMock

from llm_eval import (
    LLMEvalResult,
    build_llm_candidate_summary,
    _build_prompt,
    _parse_response,
    _call_llm_api,
    _recalc_recommend_level,
    evaluate_batch,
)


def quiet_evaluate_batch(*args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return evaluate_batch(*args, **kwargs)


# === _parse_response ===

def test_parse_response_plain_json():
    result = _parse_response('{"adjustment": 5, "reason": "匹配良好"}')
    assert result['adjustment'] == 5
    assert result['reason'] == "匹配良好"


def test_parse_response_json_in_markdown_block():
    text = '```json\n{"adjustment": -3, "reason": "经验不足"}\n```'
    result = _parse_response(text)
    assert result['adjustment'] == -3


def test_parse_response_json_with_surrounding_text():
    text = '根据分析，结果如下：\n{"adjustment": 0, "reason": "基本匹配"}\n请参考。'
    result = _parse_response(text)
    assert result['adjustment'] == 0


def test_parse_response_chinese_punctuation_normalized():
    text = '{"adjustment"：7，"reason"："高度匹配"}'
    result = _parse_response(text)
    assert result['adjustment'] == 7


def test_parse_response_adjustment_clamped_high():
    result = _parse_response('{"adjustment": 99, "reason": "极好"}')
    assert result['adjustment'] == 10


def test_parse_response_adjustment_clamped_low():
    result = _parse_response('{"adjustment": -50, "reason": "极差"}')
    assert result['adjustment'] == -10


def test_parse_response_float_adjustment_to_int():
    result = _parse_response('{"adjustment": 3.7, "reason": "不错"}')
    assert result['adjustment'] == 3
    assert isinstance(result['adjustment'], int)


def test_parse_response_missing_adjustment_defaults_zero():
    result = _parse_response('{"reason": "没有分数"}')
    assert result['adjustment'] == 0


def test_parse_response_empty_raises():
    raised = False
    try:
        _parse_response('')
    except ValueError:
        raised = True
    assert raised


def test_parse_response_unparseable_raises():
    raised = False
    try:
        _parse_response('这不是 JSON')
    except ValueError:
        raised = True
    assert raised


def test_parse_response_reason_truncated():
    long_reason = "A" * 200
    result = _parse_response(json.dumps({"adjustment": 0, "reason": long_reason}))
    assert len(result['reason']) == 100


# === _build_prompt ===

def test_build_prompt_returns_system_and_user():
    msgs = _build_prompt("岗位要求：Java 5年", "张三，5年Java经验")
    assert len(msgs) == 2
    assert msgs[0]['role'] == 'system'
    assert msgs[1]['role'] == 'user'
    assert "岗位要求：Java 5年" in msgs[1]['content']
    assert "张三，5年Java经验" in msgs[1]['content']


def test_build_llm_candidate_summary_compacts_api_resume_sections():
    long_responsibility = "负责 Python 数据分析、ETL 调度、Oracle 数据库开发。" * 40
    candidate = {
        "name": "张三",
        "match_score": 68,
        "recommend_level": "推荐",
        "skill_match_ratio": "3/5",
        "skill_matches": ["Python", "ETL", "Oracle"],
        "risk_flags": ["学历形式待确认：疑似非统招本科"],
        "summary": "\n".join([
            "张三，8年经验，期望北京",
            "教育经历：南京大学 计算机科学 本科 2008 2012",
            "工作经历：某证券公司 数据分析师 2020 至今",
            f"工作职责：{long_responsibility}",
            "技能标签：Python、ETL、Oracle、Python",
            "完整无关原文：" + "A" * 3000,
        ]),
        "score_explanation": ["技能分：30/50", "学历：本科等级通过，学历形式待人工确认"],
    }

    compact = build_llm_candidate_summary(candidate, max_chars=1200)

    assert len(compact) <= 1203
    assert "规则评分：68" in compact
    assert "风险提示：学历形式待确认：疑似非统招本科" in compact
    assert "教育经历：南京大学 计算机科学 本科 2008 2012" in compact
    assert "工作职责：负责 Python 数据分析" in compact
    assert "技能标签：Python、ETL、Oracle" in compact
    assert "A" * 1000 not in compact


# === _recalc_recommend_level ===

def test_recalc_strong_recommend():
    assert _recalc_recommend_level(75) == "强烈推荐"
    assert _recalc_recommend_level(100) == "强烈推荐"


def test_recalc_recommend():
    assert _recalc_recommend_level(65) == "推荐"
    assert _recalc_recommend_level(74) == "推荐"


def test_recalc_pending():
    assert _recalc_recommend_level(55) == "待定"
    assert _recalc_recommend_level(64) == "待定"
    assert _recalc_recommend_level(0) == "待定"


# === _call_llm_api (mocked HTTP) ===

@patch('llm_eval.requests')
def test_call_llm_api_success(mock_requests):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'choices': [{'message': {'content': '{"adjustment": 5, "reason": "匹配"}'}}]
    }
    mock_session = MagicMock()
    mock_session.post.return_value = mock_response
    mock_requests.Session.return_value = mock_session

    api_config = {'base_url': 'https://api.example.com/v1', 'model': 'test-model'}
    messages = [{"role": "user", "content": "test"}]
    result = _call_llm_api(messages, api_config, "fake-key")
    assert result.success is True
    assert result.adjustment == 5
    assert result.model == 'test-model'


@patch('llm_eval.requests')
def test_call_llm_api_client_error_no_retry(mock_requests):
    import contextlib, io
    import requests as real_requests
    mock_requests.exceptions = real_requests.exceptions
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_session = MagicMock()
    mock_session.post.return_value = mock_response
    mock_requests.Session.return_value = mock_session

    api_config = {'base_url': 'https://api.example.com/v1', 'model': 'test-model'}
    with contextlib.redirect_stdout(io.StringIO()):
        result = _call_llm_api([{"role": "user", "content": "test"}], api_config, "bad-key")
    assert result.success is False
    assert mock_session.post.call_count == 1


@patch('llm_eval.time.sleep')
@patch('llm_eval.requests')
def test_call_llm_api_timeout_retries(mock_requests, mock_sleep):
    import contextlib, io
    import requests as real_requests
    mock_requests.exceptions = real_requests.exceptions
    mock_session = MagicMock()
    mock_session.post.side_effect = real_requests.exceptions.Timeout("timeout")
    mock_requests.Session.return_value = mock_session

    api_config = {'base_url': 'https://api.example.com/v1', 'model': 'test-model'}
    with contextlib.redirect_stdout(io.StringIO()):
        result = _call_llm_api([{"role": "user", "content": "test"}], api_config, "key")
    assert result.success is False
    assert mock_session.post.call_count == 3


def test_call_llm_api_missing_config():
    result = _call_llm_api([{"role": "user", "content": "test"}], {}, "key")
    assert result.success is False
    assert "incomplete" in result.reason.lower()


# === evaluate_batch (mocked LLM) ===

@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_success_updates_candidate(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(
        success=True, adjustment=7, reason="高度匹配", model="test-model"
    )
    candidates = [
        {'name': '张三', 'match_score': 65, 'recommend_level': '推荐', 'summary': '5年Java'},
    ]
    result = quiet_evaluate_batch(candidates, "岗位要求", {'base_url': 'x', 'model': 'y'}, "key")
    c = result[0]
    assert c['llm_evaluated'] is True
    assert c['llm_adjustment'] == 7
    assert c['match_score'] == 72
    assert c['recommend_level'] == '推荐'
    assert c['rule_score'] == 65
    assert c['llm_model'] == 'test-model'


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_sends_compact_summary_to_llm(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=0, reason="ok", model="m")
    candidates = [{
        'name': '张三',
        'match_score': 65,
        'recommend_level': '推荐',
        'summary': '工作职责：' + ('Python 项目经验。' * 500),
    }]

    quiet_evaluate_batch(candidates, "岗位要求", {'base_url': 'x', 'model': 'y'}, "key")

    messages = mock_call.call_args.args[0]
    prompt_text = messages[1]['content']
    assert "工作职责：Python 项目经验" in prompt_text
    assert len(prompt_text) < len(candidates[0]['summary'])


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_failure_preserves_score(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=False, reason="timeout")
    candidates = [
        {'name': '李四', 'match_score': 60, 'recommend_level': '待定', 'summary': '3年Python'},
    ]
    result = quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key")
    c = result[0]
    assert c['llm_evaluated'] is False
    assert c['match_score'] == 60
    assert c['recommend_level'] == '待定'


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_score_clamped_high(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=10, reason="极好", model="m")
    candidates = [{'name': '王五', 'match_score': 95, 'recommend_level': '强烈推荐', 'summary': '10年'}]
    result = quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key")
    assert result[0]['match_score'] == 100


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_score_clamped_low(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=-10, reason="不匹配", model="m")
    candidates = [{'name': '赵六', 'match_score': 55, 'recommend_level': '待定', 'summary': '1年'}]
    result = quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key")
    assert result[0]['match_score'] == 45


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_level_upgrade(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=10, reason="极好", model="m")
    candidates = [{'name': 'A', 'match_score': 66, 'recommend_level': '推荐', 'summary': 'x'}]
    result = quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key")
    assert result[0]['match_score'] == 76
    assert result[0]['recommend_level'] == '强烈推荐'


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_max_candidates_limit(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=0, reason="ok", model="m")
    candidates = [
        {'name': f'C{i}', 'match_score': 60, 'recommend_level': '待定', 'summary': 'x'}
        for i in range(10)
    ]
    quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key", max_candidates=3)
    assert mock_call.call_count == 3


@patch('llm_eval._call_llm_api')
def test_batch_stop_event_interrupts(mock_call):
    import contextlib, io
    mock_call.return_value = LLMEvalResult(success=True, adjustment=0, reason="ok", model="m")
    stop_event = threading.Event()
    stop_event.set()
    candidates = [
        {'name': f'C{i}', 'match_score': 60, 'recommend_level': '待定', 'summary': 'x'}
        for i in range(5)
    ]
    with contextlib.redirect_stdout(io.StringIO()):
        quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key",
                             stop_event=stop_event)
    assert mock_call.call_count == 0


def test_batch_empty_candidates():
    result = quiet_evaluate_batch([], "岗位", {}, "key")
    assert result == []


@patch('llm_eval.time.sleep')
@patch('llm_eval._call_llm_api')
def test_batch_progress_callback(mock_call, mock_sleep):
    mock_call.return_value = LLMEvalResult(success=True, adjustment=0, reason="ok", model="m")
    progress_calls = []
    def on_progress(pct, desc):
        progress_calls.append((pct, desc))
    candidates = [
        {'name': 'A', 'match_score': 60, 'recommend_level': '待定', 'summary': 'x'},
        {'name': 'B', 'match_score': 58, 'recommend_level': '待定', 'summary': 'y'},
    ]
    quiet_evaluate_batch(candidates, "岗位", {'base_url': 'x', 'model': 'y'}, "key",
                         progress_callback=on_progress)
    assert len(progress_calls) == 3
    assert "AI 评估中" in progress_calls[0][1]
    assert "0/2" in progress_calls[0][1]  # 初始进度
    assert "AI 评估中" in progress_calls[1][1]  # 第一个完成
