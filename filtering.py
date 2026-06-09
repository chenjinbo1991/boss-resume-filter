"""Pure candidate filtering rules for BOSS resume screening."""
from __future__ import annotations

import re
from typing import Any, Optional

from constants import (
    MAJOR_CITIES,
    SCORE_BASE,
    SCORE_SKILL_MAX,
    SCORE_EXP_MAX,
    SCORE_EXP_MULTIPLIER,
    SCORE_EDU_DOCTOR,
    SCORE_EDU_MASTER_985,
    SCORE_EDU_MASTER,
    SCORE_EDU_BACHELOR_985,
    SCORE_EDU_BACHELOR,
    SCORE_THRESHOLD_PASS,
    SCORE_THRESHOLD_RECOMMEND,
    SCORE_THRESHOLD_STRONG,
    CHINESE_NUMERALS,
    NON_REGULAR_EDU,
)


_major_cities_set = set(MAJOR_CITIES)
_PREFERRED_BONUS_MAX = 10


_CERT_ALIASES = {
    '证券从业资格': ['证券从业', '证券行业', '证券相关', '证券背景', '证券经验'],
    '基金从业资格': ['基金从业', '基金行业', '基金相关', '基金背景'],
    '期货从业资格': ['期货从业', '期货行业', '期货相关'],
    '银行从业资格': ['银行从业', '银行业', '银行相关'],
    'CFA': ['cfa', 'CFA', '特许金融分析师'],
    'CPA': ['cpa', 'CPA', '注册会计师'],
    'FRM': ['frm', 'FRM', '金融风险管理师'],
}

_INDUSTRY_ALIASES = {
    '债券': ['固收', '固定收益', '利率债', '信用债', '国债', '公司债', '企业债', '可转债'],
    '基金': ['公募', '私募', 'ETF', 'FOF', '货币基金', '债券基金', '股票基金'],
    '期货': ['商品期货', '金融期货', '股指期货', 'CTA'],
    '期权': ['衍生品', '结构化产品', '场外期权', '场内期权'],
    '量化': ['量化交易', '量化策略', '量化模型', '因子模型', 'alpha策略'],
    '证券': ['券商', '证券公司', '证券交易'],
}

_EDU_ALIASES = {
    '985 院校': ['985', '985院校', '985高校', '985大学'],
    '211 院校': ['211', '211院校', '211高校', '211大学'],
    '双一流院校': ['双一流', '双一流院校', '双一流高校', '双一流大学'],
    '全日制本科': ['全日制本科', '统招本科'],
}

_SKILL_ALIASES = {
    'AI Agent': ['Agent', 'AIAgent', '智能体', '大模型Agent', '大模型 Agent'],
}


def _text_snippet(text: str, start: int, end: int, radius: int = 18) -> str:
    """Return a compact evidence snippet around a matched span."""
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace('\n', ' ').strip()
    if left > 0:
        snippet = '...' + snippet
    if right < len(text):
        snippet += '...'
    return snippet


def _find_item_evidence(candidate_text: str, item: str) -> str:
    """Find a short candidate-text snippet for a keyword or aliased condition."""
    special_exp = re.match(r'(.+?)经验≥(\d+)年$', item)
    if special_exp:
        item = special_exp.group(1).strip()

    terms = [item]
    terms.extend(_CERT_ALIASES.get(item, []))
    terms.extend(_INDUSTRY_ALIASES.get(item, []))
    terms.extend(_EDU_ALIASES.get(item, []))
    terms.extend(_SKILL_ALIASES.get(item, []))

    for term in terms:
        if not term:
            continue
        if any('一' <= c <= '鿿' for c in term):
            idx = candidate_text.lower().find(term.lower())
            if idx >= 0:
                return _text_snippet(candidate_text, idx, idx + len(term))
            continue
        try:
            match = re.search(r'\b' + re.escape(term) + r'\b', candidate_text, re.IGNORECASE)
        except re.error:
            match = None
        if match:
            return _text_snippet(candidate_text, match.start(), match.end())
        idx = candidate_text.lower().find(term.lower())
        if idx >= 0:
            return _text_snippet(candidate_text, idx, idx + len(term))
    return ""


def _condition_item_found(candidate_text: str, item: str) -> bool:
    """Match a required/preferred item with known aliases."""
    special_exp = re.match(r'(.+?)经验≥(\d+)年$', item)
    if special_exp:
        domain = special_exp.group(1).strip()
        required_years = int(special_exp.group(2))
        return _condition_item_found(candidate_text, domain) and (parse_experience_years(candidate_text) or 0) >= required_years

    if item.lower() in candidate_text.lower():
        return True
    aliases = (
        _CERT_ALIASES.get(item, [])
        + _INDUSTRY_ALIASES.get(item, [])
        + _EDU_ALIASES.get(item, [])
        + _SKILL_ALIASES.get(item, [])
    )
    return any(alias.lower() in candidate_text.lower() for alias in aliases)


def _extract_city(text: str) -> str:
    """从候选人摘要中提取期望城市名"""
    if not text:
        return ""
    city_match = re.search(r'(?:意向|城市|地点)[：:\s]*([一-龥]{2,4})', text)
    if city_match:
        raw = city_match.group(1)
        m = re.match(r'([一-龥]{2,3})市', raw)
        if m and m.group(1) in _major_cities_set:
            return m.group(1)
        if raw in _major_cities_set:
            return raw
    for city in MAJOR_CITIES:
        if city in text:
            return city
    return ""


def parse_experience_years(text: str) -> Optional[int]:
    """从文本中解析工作年限，支持阿拉伯数字和中文数字。"""

    text = text.replace(' ', '')

    # [^\S\n]* 匹配空白但不含换行，防止跨行匹配（如 "性别：0\n年龄" 中的 0+\n+年）
    arabic_match = re.search(r'(\d+)[^\S\n]*年', text)
    if arabic_match:
        return int(arabic_match.group(1))

    chinese_match = re.search(r'([零一二三四五六七八九十两]+(?:十[一二三四五六七八九两]?)?)[^\S\n]*年', text)
    if chinese_match:
        chinese_num = chinese_match.group(1)

        if chinese_num == '十':
            return 10
        elif chinese_num.startswith('十') and len(chinese_num) > 1:
            return 10 + CHINESE_NUMERALS.get(chinese_num[1], 0)
        elif chinese_num.endswith('十') and len(chinese_num) > 1:
            return CHINESE_NUMERALS.get(chinese_num[0], 0) * 10
        elif len(chinese_num) == 2:
            first = CHINESE_NUMERALS.get(chinese_num[0], 0)
            second = CHINESE_NUMERALS.get(chinese_num[1], 0)
            if first >= 2 and first <= 9:
                return first * 10 + second
            else:
                return first + second
        elif chinese_num in CHINESE_NUMERALS:
            return CHINESE_NUMERALS[chinese_num]

        result = 0
        for char in chinese_num:
            if char in CHINESE_NUMERALS:
                result += CHINESE_NUMERALS[char]
        if result > 0:
            return result

    return None


def _parse_candidate_salary_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """从候选人 summary 第一行提取期望薪资范围，单位 K。"""
    if not text:
        return None, None
    first_line = text.split('\n')[0].strip()
    if '面议' in first_line:
        return None, None
    m = re.search(r'(\d+)\s*[kK]?\s*[-~～\-]\s*(\d+)\s*[kK]', first_line)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'^(\d+)\s*[kK]', first_line)
    if m:
        val = int(m.group(1))
        return val, val
    return None, None


def _keyword_found(text: str, keyword: str) -> bool:
    """检查关键词是否在文本中作为独立词出现，避免英文子串误匹配。"""
    if keyword in _SKILL_ALIASES:
        return _condition_item_found(text, keyword)
    if any('一' <= c <= '鿿' for c in keyword):
        return keyword.lower() in text.lower()
    try:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE))
    except re.error:
        return keyword.lower() in text.lower()


def _calc_edu_bonus(text: str) -> int:
    """计算学历加分（0~10）"""
    bonus = 0
    has_985211 = any(mark in text for mark in ['985', '211', '双一流'])
    is_doctor = '博士' in text
    is_master = '硕士' in text
    is_bachelor = '本科' in text

    if is_doctor:
        bonus = SCORE_EDU_DOCTOR
    elif is_master:
        bonus = SCORE_EDU_MASTER_985 if has_985211 else SCORE_EDU_MASTER
    elif is_bachelor:
        bonus = SCORE_EDU_BACHELOR_985 if has_985211 else SCORE_EDU_BACHELOR

    return bonus


def _has_non_regular_edu_risk(text: str) -> bool:
    """Return True when text contains words that may indicate non-regular education."""
    return any(ne in text for ne in NON_REGULAR_EDU)


def _add_risk_flag(details: dict[str, Any], flag: str) -> None:
    """Attach a manual-review risk flag to filter details."""
    risk_flags = details.setdefault('risk_flags', [])
    if flag not in risk_flags:
        risk_flags.append(flag)
    details['manual_review_required'] = True
    details['auto_greet_blocked_reason'] = "学历形式待确认"


def filter_candidate(candidate_text: str, rule: dict[str, Any]) -> tuple[bool, int, dict[str, Any]]:
    """候选人筛选逻辑，返回 (passed, score, details)。"""
    try:
        details: dict[str, Any] = {
            'exp_matched': True,
            'edu_matched': True,
            'required_conditions_matched': True,
            'tech_matched': True,
            'skill_matches': [],
            'skill_total': 0,
            'skill_matched_count': 0,
            'preferred_matches': [],
            'preferred_bonus': 0,
            'exp_bonus': 0,
            'edu_bonus': 0,
            'score_breakdown': {},
            'score_explanation': [],
            'keyword_evidence': [],
            'risk_flags': [],
            'manual_review_required': False,
            'auto_greet_blocked_reason': ''
        }
        hard_checks: list[str] = []

        edu_bonus = 0
        if rule.get("edu", "不限") != "不限":
            edu_keywords = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "高中": 2, "中专": 1}
            candidate_edu_level = max(
                [edu_keywords.get(word, 0) for word in edu_keywords if word in candidate_text],
                default=0,
            )
            required_edu = edu_keywords.get(rule.get("edu", "不限"), 0)
            has_non_regular_risk = _has_non_regular_edu_risk(candidate_text)

            if rule.get("edu") == "本科":
                if candidate_edu_level >= 5:
                    pass
                elif candidate_edu_level == 4:
                    if has_non_regular_risk:
                        if re.search(r'(统招|全日制)\s*本科', candidate_text):
                            pass
                        else:
                            _add_risk_flag(details, "学历形式待确认：疑似非统招本科")
                            hard_checks.append("学历：本科等级通过，学历形式待人工确认")
                    else:
                        hard_checks.append(f"学历：通过，要求{rule.get('edu')}")
                elif has_non_regular_risk:
                    _add_risk_flag(details, "学历形式待确认：疑似非统招本科")
                    hard_checks.append("学历：疑似本科路径，学历形式待人工确认")
                else:
                    return False, 0, {"reason": "学历不足：要求本科"}
            elif required_edu > 0 and candidate_edu_level < required_edu:
                return False, 0, {"reason": f"学历不足：要求{rule.get('edu')}，实际未达要求"}

            edu_bonus = _calc_edu_bonus(candidate_text)
            hard_checks.append(f"学历加分：{edu_bonus}")
        else:
            hard_checks.append("学历：未设置硬性要求")
        details['edu_bonus'] = edu_bonus

        min_exp = rule.get("min_exp", 0)
        if min_exp > 0:
            exp_years = parse_experience_years(candidate_text)
            if exp_years is not None:
                if min_exp > exp_years:
                    return False, 0, {"reason": f"经验不足：要求{min_exp}年，实际{exp_years}年"}
                details['exp_bonus'] = min((exp_years - min_exp) * SCORE_EXP_MULTIPLIER, SCORE_EXP_MAX)
                hard_checks.append(f"经验：通过，要求{min_exp}年，实际{exp_years}年，超额加分{details['exp_bonus']}")
            else:
                hard_checks.append(f"经验：未识别明确年限，要求{min_exp}年")
        else:
            hard_checks.append("经验：未设置硬性要求")

        max_age = rule.get("max_age")
        if max_age is not None:
            age_match = re.search(r'(?:年龄[：:\s]*)?(\d+)\s*岁', candidate_text)
            if age_match and int(age_match.group(1)) > max_age:
                return False, 0, {"reason": f"年龄不符：要求≤{max_age}岁，实际{age_match.group(1)}岁"}
            if age_match:
                hard_checks.append(f"年龄：通过，要求≤{max_age}岁，实际{age_match.group(1)}岁")
            else:
                hard_checks.append(f"年龄：未识别明确年龄，要求≤{max_age}岁")

        work_location = rule.get("work_location")
        if work_location and work_location.strip():
            candidate_city = _extract_city(candidate_text)
            required_locations = re.split(r'[/、/]', work_location)
            required_locations = [loc.strip() for loc in required_locations if loc.strip()]
            if candidate_city and required_locations:
                if not any(loc in candidate_city for loc in required_locations):
                    return False, 0, {"reason": f"地点不符：要求{work_location}，期望{candidate_city}"}
                hard_checks.append(f"地点：通过，要求{work_location}，期望{candidate_city}")
            else:
                hard_checks.append(f"地点：未识别明确城市，要求{work_location}")

        salary_max = rule.get("salary_max")
        if rule.get("salary_min") is not None and salary_max is not None:
            cand_min_k, _ = _parse_candidate_salary_range(candidate_text)
            if cand_min_k is not None and cand_min_k >= salary_max + 1:
                return False, 0, {"reason": f"薪资不匹配：岗位最高{salary_max}K，候选人期望最低{cand_min_k}K"}
            if cand_min_k is not None:
                hard_checks.append(f"薪资：通过，岗位最高{salary_max}K，候选人期望最低{cand_min_k}K")
            else:
                hard_checks.append(f"薪资：未识别明确期望，岗位最高{salary_max}K")

        for condition in rule.get("required_conditions", []):
            cond_result = check_required_condition(candidate_text, condition)
            if not cond_result['passed']:
                return False, 0, {"reason": cond_result['reason']}
            for flag in cond_result.get('risk_flags', []):
                _add_risk_flag(details, flag)
            hard_checks.append(f"必要条件：通过，{condition}")
        details['required_conditions_matched'] = True

        tech_keywords_or = rule.get("tech_conditions", [])
        if tech_keywords_or:
            tech_found = any(tech.lower() in candidate_text.lower() for tech in tech_keywords_or)
            if not tech_found:
                return False, 0, {"reason": f"技术不匹配：需要{tech_keywords_or}中至少一项"}
            hard_checks.append(f"技术条件：通过，{tech_keywords_or} 至少一项")
        details['tech_matched'] = True

        keywords = rule.get("keywords", [])
        skill_score = 0
        total_possible_weight = 0
        matched_skills = []
        keyword_evidence = []

        if keywords:
            for keyword in keywords:
                if isinstance(keyword, dict):
                    kw_name = keyword.get("name", "")
                    kw_weight = keyword.get("weight", 1)
                else:
                    kw_name = keyword
                    kw_weight = 1

                total_possible_weight += kw_weight
                if _keyword_found(candidate_text, kw_name):
                    matched_skills.append(kw_name)
                    skill_score += kw_weight
                    evidence = _find_item_evidence(candidate_text, kw_name)
                    keyword_evidence.append({
                        'type': 'skill',
                        'name': kw_name,
                        'weight': kw_weight,
                        'evidence': evidence
                    })

            details['skill_matched_count'] = len(matched_skills)
            details['skill_matches'] = matched_skills
            details['skill_total'] = total_possible_weight

        if total_possible_weight > 0:
            skill_score_normalized = int((skill_score / total_possible_weight) * SCORE_SKILL_MAX)
        else:
            skill_score_normalized = SCORE_SKILL_MAX

        preferred_bonus = 0
        preferred_matches = []
        for keyword in rule.get("preferred_keywords", []):
            if isinstance(keyword, dict):
                kw_name = keyword.get("name", "")
                kw_bonus = keyword.get("bonus", keyword.get("weight", 1))
            else:
                kw_name = keyword
                kw_bonus = 1
            if kw_name and _condition_item_found(candidate_text, kw_name):
                preferred_matches.append(kw_name)
                preferred_bonus += int(kw_bonus)
                evidence = _find_item_evidence(candidate_text, kw_name)
                keyword_evidence.append({
                    'type': 'preferred',
                    'name': kw_name,
                    'weight': int(kw_bonus),
                    'evidence': evidence
                })
        preferred_bonus = min(preferred_bonus, _PREFERRED_BONUS_MAX)
        details['preferred_matches'] = preferred_matches
        details['preferred_bonus'] = preferred_bonus

        score = SCORE_BASE + skill_score_normalized + details['exp_bonus'] + details['edu_bonus'] + preferred_bonus
        score = min(score, 100)
        details['keyword_evidence'] = keyword_evidence
        details['score_breakdown'] = {
            'base': SCORE_BASE,
            'skill': skill_score_normalized,
            'experience': details['exp_bonus'],
            'education': details['edu_bonus'],
            'preferred': preferred_bonus,
            'total': score
        }
        details['score_explanation'] = [
            f"基础分：{SCORE_BASE}",
            f"技能分：{skill_score_normalized}/{SCORE_SKILL_MAX}，命中 {len(matched_skills)} 个关键词，权重 {skill_score}/{total_possible_weight or 0}",
            f"经验加分：{details['exp_bonus']}/{SCORE_EXP_MAX}",
            f"学历加分：{details['edu_bonus']}",
            f"优先项加分：{preferred_bonus}/{_PREFERRED_BONUS_MAX}",
            *hard_checks
        ]
        return True, score, details

    except Exception as e:
        return False, 0, {"reason": f"筛选异常: {str(e)[:50]}"}


def check_required_condition(candidate_text: str, condition: str | dict[str, Any]) -> dict[str, Any]:
    """检查单个必要条件。"""
    if isinstance(condition, str):
        if condition == "统招本科":
            if "硕士" in candidate_text or "博士" in candidate_text:
                return {"passed": True, "reason": ""}
            if re.search(r'(统招|全日制)\s*本科', candidate_text):
                return {"passed": True, "reason": ""}

            has_regular_mark = "985" in candidate_text or "211" in candidate_text
            has_bachelor = "本科" in candidate_text
            is_non_regular = _has_non_regular_edu_risk(candidate_text)
            if has_regular_mark and has_bachelor and not is_non_regular:
                return {"passed": True, "reason": ""}
            if is_non_regular:
                return {
                    "passed": True,
                    "reason": "",
                    "risk_flags": ["学历形式待确认：疑似非统招本科"],
                    "manual_review_required": True,
                }
            if has_bachelor:
                return {"passed": True, "reason": ""}
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}

        if not _condition_item_found(candidate_text, condition):
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}
        return {"passed": True, "reason": ""}

    elif isinstance(condition, dict):
        cond_type = condition.get("type", "or")
        items = condition.get("items", [])

        if not items:
            return {"passed": True, "reason": ""}

        if cond_type == "or":
            matched = any(_condition_item_found(candidate_text, item) for item in items)
            if not matched:
                return {"passed": False, "reason": f"必要条件不满足：需要{items}中至少一项"}
            return {"passed": True, "reason": ""}

        elif cond_type == "and":
            for item in items:
                if not _condition_item_found(candidate_text, item):
                    return {"passed": False, "reason": f"必要条件不满足：缺少{item}"}
            return {"passed": True, "reason": ""}

    return {"passed": True, "reason": ""}


def evaluate_candidate(candidate_text: str, rule: dict[str, Any]) -> bool:
    """兼容旧版本的布尔筛选接口。"""
    passed, score, details = filter_candidate(candidate_text, rule)
    return passed
