import bossmaster
from filtering import (
    _calc_edu_bonus,
    _keyword_found,
    _parse_candidate_salary_range,
    check_required_condition,
    filter_candidate,
    parse_experience_years,
)
from storage import load_candidates_all, save_candidates_all
from doc_parser import _extract_salary_range
from constants import SCORE_THRESHOLD_STRONG
import contextlib
import io
import json
import os
import tempfile
from unittest.mock import patch


def test_parse_experience_years_supports_arabic_and_chinese_numbers():
    cases = {
        "3 年经验": 3,
        "三年以上 Java 经验": 3,
        "十二年开发经验": 12,
        "两年工作经验": 2,
        "没有年限": None,
    }
    for text, expected in cases.items():
        assert parse_experience_years(text) == expected, text


def test_bossmaster_keeps_filtering_compatibility_exports():
    assert bossmaster.filter_candidate is filter_candidate
    assert bossmaster.check_required_condition is check_required_condition
    assert bossmaster.parse_experience_years is parse_experience_years


def test_bossmaster_keeps_storage_compatibility_exports():
    assert bossmaster.load_candidates_all is load_candidates_all
    assert bossmaster.save_candidates_all is save_candidates_all


def test_extract_job_salary_range_handles_numeric_and_negotiable_text():
    assert _extract_salary_range("薪资范围：12k-15k") == (12, 15)
    assert _extract_salary_range("月薪: 20K-30K") == (20, 30)
    assert _extract_salary_range("薪资面议") == (None, None)
    assert _extract_salary_range("薪资可谈") == (None, None)


def test_parse_candidate_salary_range_from_summary_first_line():
    assert _parse_candidate_salary_range("15-16K\n统招本科，5 年 Java") == (15, 16)
    assert _parse_candidate_salary_range("20-35K·15薪\n本科") == (20, 35)
    assert _parse_candidate_salary_range("18K\n本科") == (18, 18)
    assert _parse_candidate_salary_range("面议\n本科") == (None, None)


def test_keyword_matching_uses_word_boundaries_for_english_terms():
    assert _keyword_found("AI Agent and LLM platform", "AI") is True
    assert _keyword_found("email platform", "AI") is False
    assert _keyword_found("熟悉智能体和知识库", "智能体") is True


def test_education_bonus_tiers_are_stable():
    assert _calc_edu_bonus("博士学历") == 10
    assert _calc_edu_bonus("211 硕士") == 9
    assert _calc_edu_bonus("硕士") == 7
    assert _calc_edu_bonus("985 本科") == 6
    assert _calc_edu_bonus("统招本科") == 3


def test_required_conditions_support_string_or_and():
    assert check_required_condition("统招本科，5 年 Java", "统招本科")["passed"] is True
    assert check_required_condition("成教本科，5 年 Java", "统招本科")["passed"] is False

    workflow = {"type": "or", "items": ["activiti", "camunda", "flowable"]}
    assert check_required_condition("有 Camunda 项目经验", workflow)["passed"] is True
    assert check_required_condition("只有 Spring Boot 经验", workflow)["passed"] is False

    stack = {"type": "and", "items": ["Java", "MySQL", "Redis"]}
    assert check_required_condition("Java MySQL Redis", stack)["passed"] is True
    assert check_required_condition("Java MySQL", stack)["passed"] is False


def test_filter_candidate_scores_and_hard_rejections_are_stable():
    rule = {
        "min_exp": 4,
        "edu": "本科",
        "work_location": "南京",
        "salary_min": 12,
        "salary_max": 15,
        "required_conditions": ["统招本科"],
        "keywords": [
            {"name": "Java", "weight": 2},
            {"name": "Spring Cloud", "weight": 2},
            {"name": "MySQL", "weight": 1},
            {"name": "Redis", "weight": 1},
        ],
    }

    passed, score, details = filter_candidate(
        "15-16K\n南京，统招本科，6 年 Java 经验，熟悉 Spring Cloud、MySQL、Redis",
        rule,
    )
    assert passed is True
    assert score >= SCORE_THRESHOLD_STRONG
    assert details["skill_matched_count"] == 4

    passed, _, details = filter_candidate(
        "18-22K\n南京，统招本科，6 年 Java 经验，熟悉 Spring Cloud、MySQL、Redis",
        rule,
    )
    assert passed is False
    assert "薪资不匹配" in details["reason"]

    passed, _, details = filter_candidate(
        "15-16K\n上海，统招本科，6 年 Java 经验，熟悉 Spring Cloud、MySQL、Redis",
        rule,
    )
    assert passed is False
    assert "地点不符" in details["reason"]


def test_filter_candidate_age_boundaries_are_stable():
    rule = {
        "min_exp": 0,
        "edu": "不限",
        "max_age": 35,
        "keywords": ["Java"],
    }

    passed, _, _ = filter_candidate("35岁，Java 开发", rule)
    assert passed is True

    passed, _, details = filter_candidate("年龄：36 岁，Java 开发", rule)
    assert passed is False
    assert "年龄不符" in details["reason"]


def test_filter_candidate_rejects_non_regular_bachelor_even_with_school_mark():
    rule = {
        "min_exp": 0,
        "edu": "本科",
        "required_conditions": ["统招本科"],
        "keywords": ["Java"],
    }

    passed, _, details = filter_candidate("985 本科，专升本，5 年 Java", rule)
    assert passed is False
    assert "学历不符" in details["reason"] or "非统招" in details["reason"]

    passed, _, _ = filter_candidate("全日制本科，5 年 Java", rule)
    assert passed is True


def test_save_candidates_all_deduplicates_by_geek_id_and_job_name():
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            with contextlib.redirect_stdout(io.StringIO()):
                save_candidates_all([
                    {
                        "geek_id": "g1",
                        "job_name": "Java",
                        "match_score": 70,
                        "greet_sent": True,
                        "greeting_in_progress": True,
                    },
                    {
                        "geek_id": "g1",
                        "job_name": "Java",
                        "match_score": 80,
                        "greet_sent": False,
                    },
                    {
                        "geek_id": "g1",
                        "job_name": "Python",
                        "match_score": 60,
                        "greet_sent": False,
                    },
                ])

            with open("candidates_all.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
        finally:
            os.chdir(old_cwd)

    assert len(saved) == 2
    java = next(c for c in saved if c["job_name"] == "Java")
    python = next(c for c in saved if c["job_name"] == "Python")
    assert java["match_score"] == 80
    assert java["greet_sent"] is True
    assert "greeting_in_progress" not in java
    assert python["match_score"] == 60


def test_save_candidates_all_filters_below_55():
    """低于 55 分的候选人不应写入 candidates_all.json"""
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            with contextlib.redirect_stdout(io.StringIO()):
                save_candidates_all([
                    {"geek_id": "g1", "job_name": "Java", "match_score": 80},
                    {"geek_id": "g2", "job_name": "Java", "match_score": 55},
                    {"geek_id": "g3", "job_name": "Java", "match_score": 54},
                    {"geek_id": "g4", "job_name": "Java", "match_score": 30},
                ])

            with open("candidates_all.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
        finally:
            os.chdir(old_cwd)

    assert len(saved) == 2
    ids = {c["geek_id"] for c in saved}
    assert ids == {"g1", "g2"}


def test_load_candidates_all_restores_from_backup_when_main_json_is_corrupt():
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            os.chdir(tmpdir)
            backup_data = [{"geek_id": "g1", "job_name": "Java", "greet_sent": True}]
            with open("candidates_all.json", "w", encoding="utf-8") as f:
                f.write("{broken json")
            with open("candidates_all.json.bak", "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False)

            with contextlib.redirect_stdout(io.StringIO()):
                loaded = load_candidates_all()

            with open("candidates_all.json", "r", encoding="utf-8") as f:
                restored = json.load(f)
        finally:
            os.chdir(old_cwd)

    assert loaded == backup_data
    assert restored == backup_data


def test_save_candidates_all_accepts_explicit_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "nested_candidates.json")
        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all([
                {"geek_id": "g1", "job_name": "Java", "match_score": 70},
            ], target)

        with open(target, "r", encoding="utf-8") as f:
            saved = json.load(f)

    assert saved == [{"geek_id": "g1", "job_name": "Java", "match_score": 70}]


# ========== load_job_config ==========

def test_load_job_config_jobs_key_format():
    """支持 "jobs" 键格式的配置文件。"""
    config = {
        "jobs": {
            "Java工程师": {
                "min_exp": 3,
                "edu": "本科",
                "keywords": ["Java", "Spring"]
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            jobs, default = load_job_config()
        assert "Java工程师" in jobs
        assert default is None
        assert jobs["Java工程师"]["min_exp"] == 3
    finally:
        os.unlink(tmp_path)


def test_load_job_config_extracts_default_rule():
    """default 规则应从 job_requirements 中提取出来单独返回。"""
    config = {
        "job_requirements": {
            "default": {"min_exp": 0, "edu": "不限", "keywords": []},
            "Python工程师": {"min_exp": 2, "keywords": ["Python"]},
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            jobs, default = load_job_config()
        assert "default" not in jobs
        assert default is not None
        assert default["edu"] == "不限"
        assert "Python工程师" in jobs
    finally:
        os.unlink(tmp_path)


def test_load_job_config_strips_spaces_from_job_name():
    """岗位名称中的空格应被移除。"""
    config = {"jobs": {"Java 工程师": {"keywords": ["Java"]}}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            jobs, _ = load_job_config()
        assert "Java工程师" in jobs
        assert "Java 工程师" not in jobs
    finally:
        os.unlink(tmp_path)


def test_load_job_config_deduplicates_keywords_case_insensitive():
    """关键词应按小写去重，保留首次出现的格式。"""
    config = {
        "jobs": {
            "Dev": {
                "keywords": ["Java", "java", "JAVA", "Spring"]
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            jobs, _ = load_job_config()
        kws = jobs["Dev"]["keywords"]
        assert len(kws) == 2  # Java (case-insensitive dedup) + Spring
        assert kws[0] == "Java"  # 保留首次出现
        assert "Spring" in kws
    finally:
        os.unlink(tmp_path)


def test_load_job_config_deduplicates_dict_format_keywords():
    """dict 格式关键词也应按 name 去重。"""
    config = {
        "jobs": {
            "Dev": {
                "keywords": [
                    {"name": "Java", "weight": 2},
                    {"name": "java", "weight": 1},
                    {"name": "Spring", "weight": 1},
                ]
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False)
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            jobs, _ = load_job_config()
        kws = jobs["Dev"]["keywords"]
        assert len(kws) == 2
        assert kws[0]["name"] == "Java"
        assert kws[0]["weight"] == 2  # 保留首次出现的 weight
    finally:
        os.unlink(tmp_path)


def test_load_job_config_missing_file_returns_default():
    """配置文件不存在时返回默认配置。"""
    with patch('bossmaster.CONFIG_PATH', '/nonexistent/path/job_config.json'):
        from bossmaster import load_job_config
        with contextlib.redirect_stdout(io.StringIO()):
            jobs, default = load_job_config()
        assert default is None
        assert "default" in jobs
        assert jobs["default"]["edu"] == "不限"


def test_load_job_config_corrupt_json_returns_default():
    """配置文件 JSON 损坏时返回默认配置。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        f.write("{broken json")
        tmp_path = f.name
    try:
        with patch('bossmaster.CONFIG_PATH', tmp_path):
            from bossmaster import load_job_config
            with contextlib.redirect_stdout(io.StringIO()):
                jobs, default = load_job_config()
        assert default is None
        assert "default" in jobs
    finally:
        os.unlink(tmp_path)


# ========== extract_summary_info ==========

def test_extract_summary_info_full_text():
    """完整摘要文本应提取所有字段。"""
    from bossmaster import extract_summary_info
    text = "15-20K\n30 岁，6 年经验，本科\n离职-某某科技有限公司\n南京\n熟悉 Java、Spring、MySQL、Redis"
    info = extract_summary_info(text)
    assert info['salary'] == '15-20K'
    assert info['age'] == '30'
    assert info['exp_years'] == '6'
    assert info['education'] == '本科'
    assert info['job_status'] == '离职'
    assert '某某科技' in info['company']
    assert 'Java' in info['skills']
    assert 'MySQL' in info['skills']


def test_extract_summary_info_negotiable_salary():
    """面议薪资应正确识别。"""
    from bossmaster import extract_summary_info
    info = extract_summary_info("面议\n本科，3 年经验")
    assert info['salary'] == '面议'


def test_extract_summary_info_empty_text():
    """空文本应返回全空字典。"""
    from bossmaster import extract_summary_info
    info = extract_summary_info("")
    assert all(v == '' for v in info.values())


def test_extract_summary_info_education_priority():
    """学历应取最高级别（博士 > 硕士 > 本科）。"""
    from bossmaster import extract_summary_info
    info = extract_summary_info("本科，硕士在读，博士毕业")
    assert info['education'] == '博士'


def test_extract_summary_info_status_with_company():
    """在职/离职状态和公司名提取。"""
    from bossmaster import extract_summary_info
    info = extract_summary_info("在职-阿里巴巴集团")
    assert info['job_status'] == '在职'
    assert info['company'] == '阿里巴巴集团'
