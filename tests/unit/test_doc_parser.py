"""Tests for doc_parser.parse_job_requirements() — the 530-line requirement parsing engine."""
from doc_parser import parse_job_requirements, _resolve_city, _extract_work_location


# ========== 城市提取 ==========

def test_resolve_city_with_suffix():
    assert _resolve_city("南京市雨花区") == "南京"
    assert _resolve_city("上海市浦东") == "上海"
    assert _resolve_city("哈尔滨市") == "哈尔滨"


def test_resolve_city_without_suffix():
    assert _resolve_city("深圳南山") == "深圳"
    assert _resolve_city("成都高新区") == "成都"


def test_resolve_city_unknown_returns_empty():
    assert _resolve_city("吉林市") == ""
    assert _resolve_city("未知地区") == ""
    assert _resolve_city("") == ""


def test_extract_work_location_patterns():
    assert _extract_work_location("工作地点：南京市雨花区凯润大厦") == "南京"
    assert _extract_work_location("base：上海浦东") == "上海"
    assert _extract_work_location("坐标：成都高新区") == "成都"
    assert _extract_work_location("Base地：深圳南山") == "深圳"


def test_extract_work_location_fallback_scans_full_text():
    assert _extract_work_location("我们在杭州招聘优秀人才") == "杭州"
    assert _extract_work_location("无地点信息") == ""


# ========== 职位名称提取 ==========

def test_job_title_markdown_heading():
    result = parse_job_requirements("# 高级 Java 开发工程师\n## 硬性条件\n本科")
    assert result["job_title"] == "高级 Java 开发工程师"


def test_job_title_bracket_format():
    result = parse_job_requirements("【高级 Python 工程师】\n职位要求\n本科")
    assert result["job_title"] == "高级 Python 工程师"


def test_job_title_colon_format():
    result = parse_job_requirements("岗位：全栈工程师\n职位要求\n本科")
    assert result["job_title"] == "全栈工程师"


def test_job_title_default_when_not_found():
    result = parse_job_requirements("需要3年以上开发经验，熟悉Java")
    assert result["job_title"] == "Java 工程师"


# ========== 经验提取 ==========

def test_experience_explicit_field():
    result = parse_job_requirements("## 硬性条件\n工作年限：5 年以上")
    assert result["min_exp"] == 5


def test_experience_range_takes_minimum():
    result = parse_job_requirements("## 硬性条件\n工作年限：3-5 年")
    assert result["min_exp"] == 3


def test_experience_markdown_bold():
    result = parse_job_requirements("## 硬性条件\n**工作年限**：5 年以上")
    assert result["min_exp"] == 5


def test_experience_from_general_text():
    result = parse_job_requirements("职位要求\n3 年以上 Java 开发经验")
    assert result["min_exp"] == 3


def test_experience_default_zero():
    result = parse_job_requirements("招聘开发人员")
    assert result["min_exp"] == 0


# ========== 学历提取 ==========

def test_education_explicit_field():
    result = parse_job_requirements("## 硬性条件\n最低学历：本科")
    assert result["edu"] == "本科"


def test_education_master():
    result = parse_job_requirements("## 硬性条件\n学历要求：硕士")
    assert result["edu"] == "硕士"


def test_education_phd_priority_excluded():
    """博士优先 不应被当作最低学历门槛"""
    result = parse_job_requirements("## 硬性条件\n本科，博士优先")
    assert result["edu"] == "本科"


def test_education_from_low_to_high():
    """从低到高判断：大专 < 本科 < 硕士 < 博士"""
    result = parse_job_requirements("## 硬性条件\n大专以上")
    assert result["edu"] == "大专"


def test_education_default_unlimited():
    result = parse_job_requirements("招聘开发人员")
    assert result["edu"] == "不限"


# ========== 必要条件提取 ==========

def test_required_conditions_tongzhao():
    result = parse_job_requirements("## 硬性条件\n统招本科，5 年经验")
    assert "统招本科" in result["required_conditions"]


def test_required_conditions_quanrizhi():
    result = parse_job_requirements("## 硬性条件\n全日制本科")
    assert "全日制" in result["required_conditions"]


def test_required_conditions_985_211():
    result = parse_job_requirements("## 硬性条件\n985/211 院校")
    assert "985 院校" in result["required_conditions"]
    assert "211 院校" in result["required_conditions"]


def test_required_conditions_age_limit():
    result = parse_job_requirements("## 硬性条件\n年龄 35 岁以下")
    assert result["max_age"] == 35
    assert "年龄≤35岁" in result["required_conditions"]


def test_required_conditions_shuangzheng():
    result = parse_job_requirements("## 硬性条件\n双证齐全")
    assert "双证齐全" in result["required_conditions"]


# ========== 技术条件关键词 ==========

def test_tech_conditions_extracted_from_required_section():
    text = "## 硬性条件\n必须熟悉 Java 或 Python"
    result = parse_job_requirements(text)
    assert "Java" in result["tech_conditions"] or "Python" in result["tech_conditions"]


def test_tech_conditions_spring_ecosystem():
    text = "## 硬性条件\nSpring Cloud 微服务经验"
    result = parse_job_requirements(text)
    assert any("Spring" in tc for tc in result["tech_conditions"])


# ========== 软技能提取 ==========

def test_soft_skills_basic_extraction():
    text = "职位描述\n熟悉 Java、Spring Boot、MySQL、Redis"
    result = parse_job_requirements(text)
    skill_names = [s for s in result["soft_skills"]]
    assert "Java" in skill_names
    assert "MySQL" in skill_names
    assert "Redis" in skill_names


def test_soft_skills_spring_cloud_normalized():
    text = "职位描述\n精通 Spring Cloud 微服务"
    result = parse_job_requirements(text)
    skill_names_lower = [s.lower() for s in result["soft_skills"]]
    assert "spring cloud" in skill_names_lower


def test_soft_skills_deduplication():
    text = "职位描述\nJava 开发，Java 经验"
    result = parse_job_requirements(text)
    java_count = sum(1 for s in result["soft_skills"] if s.lower() == "java")
    assert java_count == 1


def test_soft_skills_ai_keywords():
    text = "职位描述\nLLM 大模型开发，RAG 知识库"
    result = parse_job_requirements(text)
    skill_names_lower = [s.lower() for s in result["soft_skills"]]
    assert "llm" in skill_names_lower
    assert "rag" in skill_names_lower


# ========== 薪资范围 ==========

def test_salary_range_extracted():
    text = "薪资范围：15k-25k\n职位要求\n本科"
    result = parse_job_requirements(text)
    assert result["salary_min"] == 15
    assert result["salary_max"] == 25


def test_salary_negotiable_returns_none():
    text = "薪资面议\n职位要求\n本科"
    result = parse_job_requirements(text)
    assert result["salary_min"] is None
    assert result["salary_max"] is None


# ========== 综合集成测试 ==========

def test_full_requirement_parsing():
    """完整的招聘需求文本解析"""
    text = """# 高级 Java 开发工程师

职位描述
负责公司核心系统的后端开发，使用 Spring Cloud 微服务架构。
需要熟悉 MySQL、Redis、Kafka。

职位要求
1. 5 年以上 Java 开发经验
2. 精通 Spring Cloud、Spring Boot
3. 熟悉 Docker、Kubernetes
4. 有 LLM、大模型经验优先

## 硬性条件
**工作年限**：5 年以上
**最低学历**：本科
统招本科，985/211 优先
年龄 35 岁
工作地点：南京

薪资范围：20k-35k
"""
    result = parse_job_requirements(text)

    assert result["job_title"] == "高级 Java 开发工程师"
    assert result["min_exp"] == 5
    assert result["edu"] == "本科"
    assert result["work_location"] == "南京"
    assert result["salary_min"] == 20
    assert result["salary_max"] == 35
    assert result["max_age"] == 35
    assert "统招本科" in result["required_conditions"]

    # 软技能应包含主要技术栈
    skill_names_lower = [s.lower() for s in result["soft_skills"]]
    assert "java" in skill_names_lower
    assert "mysql" in skill_names_lower


def test_empty_text_returns_defaults():
    result = parse_job_requirements("")
    assert result["job_title"] == "Java 工程师"
    assert result["min_exp"] == 0
    assert result["edu"] == "不限"
    assert result["soft_skills"] == []
    assert result["required_conditions"] == []


def test_markdown_format_full():
    """纯 markdown 格式的招聘需求"""
    text = """# Python 后端工程师

## 硬性条件

### 工作经验
3 年以上 Python 开发

### 学历要求
本科

## 软性条件
- 熟悉 Django、Flask
- 了解 Docker
"""
    result = parse_job_requirements(text)
    assert result["job_title"] == "Python 后端工程师"
    assert result["min_exp"] == 3
    assert result["edu"] == "本科"
