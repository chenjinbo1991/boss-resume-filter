"""Tests for AI-enhanced job requirement parsing."""
import json
from unittest.mock import Mock, patch

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
    assert {"name": "证券行业", "bonus": 4} in job["preferred_keywords"]
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
    assert job["preferred_keywords"] == [{"name": "证券", "bonus": 10}]


def test_merge_patch_filters_ai_keyword_noise_and_soft_trait_conditions():
    patch_data = {
        "keywords_add": [
            {"name": "万得API", "weight": 2},
            {"name": "彭博", "weight": 2},
            {"name": "API", "weight": 2},
            {"name": "数据库技术", "weight": 3},
            {"name": "Python", "weight": 3},
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
    assert "数据库技术" not in keyword_names
    assert "具备较强的服务意识和团队精神" not in job["required_conditions"]
    assert "较强的学习能力和执行能力" not in job["required_conditions"]
    assert {"type": "or", "items": ["债券", "基金"], "category": "金融投资行业经验"} in job["required_conditions"]


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
    assert {"name": "大模型 Agent", "bonus": 3} in job["preferred_keywords"]
    assert result.warnings == ["优先项来自原文"]


@patch("job_ai_parser.requests.post")
def test_enhance_config_with_ai_failure_returns_regex_config(mock_post):
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
