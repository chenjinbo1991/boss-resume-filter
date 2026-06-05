"""Tests for AI-enhanced job requirement parsing."""
import json
from unittest.mock import Mock, patch

import requests

from job_ai_parser import (
    _merge_patch,
    _parse_json_response,
    enhance_config_with_ai,
)


def _base_config():
    return {
        "job_requirements": {
            "Java 工程师": {
                "min_exp": 3,
                "edu": "本科",
                "work_location": "南京",
                "salary_min": 12,
                "salary_max": 18,
                "keywords": [{"name": "Java", "weight": 2}],
                "preferred_keywords": [],
                "required_conditions": ["统招本科"],
            }
        }
    }


def test_parse_json_response_from_markdown_block():
    parsed = _parse_json_response('```json\n{"warnings":["需要确认"]}\n```')
    assert parsed == {"warnings": ["需要确认"]}


def test_merge_patch_adds_ai_enhancements_without_losing_regex_base():
    patch_data = {
        "job_title": "中高级 Java 工程师",
        "basic_info": {"min_exp": 5, "edu": "本科"},
        "keywords_add": [{"name": "Spring Boot", "weight": 3}],
        "preferred_keywords_add": [{"name": "证券行业", "bonus": 4}],
        "required_conditions_add": [
            {"type": "or", "items": ["债券", "基金", "期货", "期权"], "category": "金融投资行业经验"}
        ],
    }

    result = _merge_patch(_base_config(), patch_data)
    job_title = list(result["job_requirements"].keys())[0]
    job = result["job_requirements"][job_title]

    assert job_title == "中高级 Java 工程师"
    assert job["min_exp"] == 5
    assert {"name": "Java", "weight": 2} in job["keywords"]
    assert {"name": "Spring Boot", "weight": 3} in job["keywords"]
    assert {"name": "证券", "bonus": 2} in job["preferred_keywords"]
    assert {"type": "or", "items": ["债券", "基金", "期货", "期权"], "category": "金融投资行业经验"} in job["required_conditions"]


def test_merge_patch_strips_numbered_job_title_prefix():
    result = _merge_patch(_base_config(), {"job_title": "岗位1:证券固收业务python分析师"})
    assert list(result["job_requirements"].keys())[0] == "证券固收业务python分析师"


def test_merge_patch_clamps_weights_and_deduplicates():
    patch_data = {
        "keywords_add": [{"name": "Java", "weight": 99}],
        "preferred_keywords_add": [{"name": "证券", "bonus": 99}, {"name": "证券", "bonus": 1}],
    }

    job = list(_merge_patch(_base_config(), patch_data)["job_requirements"].values())[0]

    assert next(k for k in job["keywords"] if k["name"] == "Java")["weight"] == 3
    assert job["preferred_keywords"] == [{"name": "证券", "bonus": 2}]


def test_merge_patch_filters_ai_keyword_noise_and_soft_trait_conditions():
    patch_data = {
        "keywords_add": [
            {"name": "万得API", "weight": 2},
            {"name": "彭博", "weight": 2},
            {"name": "API", "weight": 2},
            {"name": "AI", "weight": 2},
            {"name": "人工智能", "weight": 2},
            {"name": "数据库技术", "weight": 3},
            {"name": "数据清洗", "weight": 2},
            {"name": "因子计算", "weight": 2},
            {"name": "报表开发", "weight": 1},
            {"name": "证券行业", "weight": 2},
            {"name": "Python", "weight": 3},
            {"name": "AI Agent", "weight": 2},
            {"name": "Spring AI", "weight": 2},
        ],
        "required_conditions_add": [
            "具备较强的服务意识和团队精神",
            "较强的学习能力和执行能力",
            {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"},
        ],
    }

    job = list(_merge_patch(_base_config(), patch_data)["job_requirements"].values())[0]
    keyword_names = [item["name"] for item in job["keywords"]]

    assert "Python" in keyword_names
    assert "万得API" not in keyword_names
    assert "彭博" not in keyword_names
    assert "API" not in keyword_names
    assert "AI" not in keyword_names
    assert "人工智能" not in keyword_names
    assert "数据库技术" not in keyword_names
    assert "数据清洗" not in keyword_names
    assert "因子计算" not in keyword_names
    assert "报表开发" not in keyword_names
    assert "证券行业" not in keyword_names
    assert "AI Agent" in keyword_names
    assert "Spring AI" in keyword_names
    assert "具备较强的服务意识和团队精神" not in job["required_conditions"]
    assert "较强的学习能力和执行能力" not in job["required_conditions"]
    assert {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"} in job["required_conditions"]


def test_merge_patch_normalizes_ai_required_education_and_experience():
    base = _base_config()
    base["job_requirements"]["Java 工程师"]["min_exp"] = 0
    base["job_requirements"]["Java 工程师"]["required_conditions"] = []

    patch_data = {
        "required_conditions_add": [
            "统招本科及以上学历",
            "5年以上相关工作经验",
            "本科及以上学历",
            {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"},
        ],
    }

    job = list(_merge_patch(base, patch_data)["job_requirements"].values())[0]

    assert job["min_exp"] == 5
    assert "统招本科" in job["required_conditions"]
    assert "统招本科及以上学历" not in job["required_conditions"]
    assert "5年以上相关工作经验" not in job["required_conditions"]
    assert "本科及以上学历" not in job["required_conditions"]
    assert {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"} in job["required_conditions"]


def test_merge_patch_normalizes_ai_work_location_to_city():
    base = _base_config()
    base["job_requirements"]["Java 工程师"]["work_location"] = "北京"

    for raw_location in ("北京丰台区", "北京市丰台区西营街青海大厦银河证券"):
        job = list(_merge_patch(base, {"basic_info": {"work_location": raw_location}})["job_requirements"].values())[0]
        assert job["work_location"] == "北京"

    job = list(_merge_patch(base, {"basic_info": {"work_location": "青海大厦"}})["job_requirements"].values())[0]
    assert job["work_location"] == "北京"


def test_merge_patch_keeps_default_max_age_when_ai_returns_null():
    base = _base_config()
    base["job_requirements"]["Java 工程师"]["max_age"] = 35

    job = list(_merge_patch(base, {"basic_info": {"max_age": None}})["job_requirements"].values())[0]
    assert job["max_age"] == 35

    job = list(_merge_patch(base, {"basic_info": {"max_age": 40}})["job_requirements"].values())[0]
    assert job["max_age"] == 40


def test_merge_patch_filters_ai_skill_requirements_from_required_conditions():
    patch_data = {
        "keywords_add": [
            {"name": "Python", "weight": 3},
            {"name": "SQL", "weight": 2},
        ],
        "required_conditions_add": [
            "具备Python语言开发经验",
            "熟练掌握SQL",
            {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"},
        ],
    }

    job = list(_merge_patch(_base_config(), patch_data)["job_requirements"].values())[0]
    keyword_names = [item["name"] for item in job["keywords"]]

    assert "Python" in keyword_names
    assert "SQL" in keyword_names
    assert "具备Python语言开发经验" not in job["required_conditions"]
    assert "熟练掌握SQL" not in job["required_conditions"]
    assert {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"} in job["required_conditions"]


def test_merge_patch_normalizes_ai_agent_keyword_names():
    patch_data = {
        "keywords_add": [
            {"name": "大模型 Agent", "weight": 2},
            {"name": "Agent", "weight": 1},
        ],
        "preferred_keywords_add": [
            {"name": "大模型Agent", "bonus": 2},
        ],
    }

    job = list(_merge_patch(_base_config(), patch_data)["job_requirements"].values())[0]

    assert {"name": "AI Agent", "weight": 2} not in job["keywords"]
    assert {"name": "AI Agent", "bonus": 2} in job["preferred_keywords"]
    assert not any(item["name"] in {"大模型 Agent", "Agent"} for item in job["keywords"])
    assert not any(item["name"] == "大模型Agent" for item in job["preferred_keywords"])


def test_merge_patch_limits_ai_preferred_bonus_and_avoids_preferred_keyword_duplicates():
    patch_data = {
        "keywords_add": [
            {"name": "AI Agent", "weight": 1},
            {"name": "全栈开发", "weight": 3},
            {"name": "数据库运维", "weight": 3},
            {"name": "数据清洗", "weight": 2},
            {"name": "因子计算", "weight": 2},
            {"name": "报表开发", "weight": 1},
            {"name": "证券行业", "weight": 5},
        ],
        "preferred_keywords_add": [
            {"name": "证券行业", "bonus": 5},
            {"name": "全栈开发", "bonus": 3},
            {"name": "数据库运维", "bonus": 3},
            {"name": "AI Agent", "bonus": 5},
        ],
    }

    job = list(_merge_patch(_base_config(), patch_data)["job_requirements"].values())[0]
    keyword_names = [item["name"] for item in job["keywords"]]

    assert "AI Agent" not in keyword_names
    assert "全栈开发" not in keyword_names
    assert "数据库运维" not in keyword_names
    assert "数据清洗" not in keyword_names
    assert "因子计算" not in keyword_names
    assert "报表开发" not in keyword_names
    assert "证券行业" not in keyword_names
    assert "证券" not in keyword_names
    assert {"name": "证券", "bonus": 2} in job["preferred_keywords"]
    assert {"name": "全栈开发", "bonus": 2} in job["preferred_keywords"]
    assert {"name": "数据库运维", "bonus": 2} in job["preferred_keywords"]
    assert {"name": "AI Agent", "bonus": 2} in job["preferred_keywords"]


def test_merge_patch_filters_ai_preferred_items_without_preferred_clause_evidence():
    requirements_text = """职位描述【中高级AI工程师】：
1. 熟练使用Spring Cloud、Dubbo或类似的微服务框架,Dubbo优先；
2. 有AI开发背景（LLM、Al Agent、智能体、Spring AI、Langchain、智能问答、知识库）的优先；"""
    base = {
        "job_requirements": {
            "中高级AI工程师": {
                "min_exp": 4,
                "edu": "本科",
                "keywords": [
                    {"name": "Spring Cloud", "weight": 2},
                    {"name": "Dubbo", "weight": 2},
                    {"name": "微服务", "weight": 2},
                ],
                "preferred_keywords": [],
                "required_conditions": [],
            }
        }
    }
    patch_data = {
        "preferred_keywords_add": [
            {"name": "Spring Cloud", "bonus": 2},
            {"name": "微服务", "bonus": 2},
            {"name": "Dubbo", "bonus": 2},
            {"name": "AI Agent", "bonus": 2},
            {"name": "Langchain", "bonus": 2},
            {"name": "Spring AI", "bonus": 2},
            {"name": "智能问答", "bonus": 2},
            {"name": "LLM", "bonus": 2},
            {"name": "知识库", "bonus": 2},
        ],
    }

    job = list(_merge_patch(base, patch_data, requirements_text)["job_requirements"].values())[0]
    preferred_names = [item["name"] for item in job["preferred_keywords"]]

    assert "Spring Cloud" not in preferred_names
    assert "微服务" not in preferred_names
    assert "Dubbo" in preferred_names
    assert "AI Agent" in preferred_names
    assert "LangChain" in preferred_names
    assert "Spring AI" in preferred_names
    assert "智能问答" in preferred_names
    assert "LLM" in preferred_names
    assert "知识库" in preferred_names


@patch("job_ai_parser.requests.post")
def test_enhance_config_with_ai_success(mock_post):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "keywords_add": [{"name": "MySQL", "weight": 2}],
                    "preferred_keywords_add": [{"name": "大模型 Agent", "bonus": 3}],
                    "warnings": ["优先项来自原文"]
                }, ensure_ascii=False)
            }
        }]
    }
    mock_post.return_value = response

    result = enhance_config_with_ai(
        "Java，MySQL，大模型 Agent 经验优先",
        _base_config(),
        {"base_url": "https://api.example.com/v1", "model": "test-model"},
        "sk-test",
    )

    job = list(result.config["job_requirements"].values())[0]
    assert result.success is True
    assert result.model == "test-model"
    assert {"name": "MySQL", "weight": 2} in job["keywords"]
    assert {"name": "AI Agent", "bonus": 2} in job["preferred_keywords"]
    assert result.warnings == ["优先项来自原文"]


@patch("job_ai_parser.time.sleep")
@patch("job_ai_parser.requests.post")
def test_enhance_config_with_ai_retries_timeout_and_succeeds(mock_post, mock_sleep):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "keywords_add": [{"name": "MySQL", "weight": 2}]
                }, ensure_ascii=False)
            }
        }]
    }
    mock_post.side_effect = [requests.exceptions.Timeout("slow"), response]

    result = enhance_config_with_ai(
        "Java，MySQL",
        _base_config(),
        {"base_url": "https://api.example.com/v1", "model": "test-model"},
        "sk-test",
    )

    job = list(result.config["job_requirements"].values())[0]
    assert result.success is True
    assert {"name": "MySQL", "weight": 2} in job["keywords"]
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()


@patch("job_ai_parser.requests.post")
def test_enhance_config_with_ai_auth_error_does_not_retry(mock_post):
    response = Mock()
    response.status_code = 401
    response.text = "unauthorized"
    mock_post.return_value = response

    result = enhance_config_with_ai(
        "Java",
        _base_config(),
        {"base_url": "https://api.example.com/v1", "model": "test-model"},
        "sk-test",
    )

    assert result.success is False
    assert "鉴权失败" in result.reason
    assert mock_post.call_count == 1


@patch("job_ai_parser.time.sleep")
@patch("job_ai_parser.requests.post")
def test_enhance_config_with_ai_failure_returns_regex_config(mock_post, mock_sleep):
    response = Mock()
    response.status_code = 500
    response.text = "server error"
    mock_post.return_value = response

    base = _base_config()
    result = enhance_config_with_ai(
        "Java",
        base,
        {"base_url": "https://api.example.com/v1", "model": "test-model"},
        "sk-test",
    )

    assert result.success is False
    assert result.config == base
    assert "服务端错误" in result.reason
    assert mock_post.call_count == 2
