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

    arabic_match = re.search(r'(\d+)\s*年', text)
    if arabic_match:
        return int(arabic_match.group(1))

    chinese_match = re.search(r'([零一二三四五六七八九十两]+(?:十[一二三四五六七八九两]?)?)\s*年', text)
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
            'exp_bonus': 0,
            'edu_bonus': 0
        }

        edu_bonus = 0
        if rule.get("edu", "不限") != "不限":
            edu_keywords = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "高中": 2, "中专": 1}
            candidate_edu_level = max([edu_keywords.get(word, 0) for word in edu_keywords if word in candidate_text])
            required_edu = edu_keywords.get(rule.get("edu", "不限"), 0)

            if rule.get("edu") == "本科":
                if candidate_edu_level >= 5:
                    pass
                elif candidate_edu_level == 4:
                    is_non_regular = any(ne in candidate_text for ne in NON_REGULAR_EDU)
                    if is_non_regular:
                        if re.search(r'(统招|全日制)\s*本科', candidate_text):
                            pass
                        else:
                            return False, 0, {"reason": "学历不符：要求统招本科"}
                else:
                    return False, 0, {"reason": "学历不足：要求本科"}
            elif required_edu > 0 and candidate_edu_level < required_edu:
                return False, 0, {"reason": f"学历不足：要求{rule.get('edu')}，实际未达要求"}

            edu_bonus = _calc_edu_bonus(candidate_text)
        details['edu_bonus'] = edu_bonus

        min_exp = rule.get("min_exp", 0)
        if min_exp > 0:
            exp_years = parse_experience_years(candidate_text)
            if exp_years is not None:
                if min_exp > exp_years:
                    return False, 0, {"reason": f"经验不足：要求{min_exp}年，实际{exp_years}年"}
                details['exp_bonus'] = min((exp_years - min_exp) * SCORE_EXP_MULTIPLIER, SCORE_EXP_MAX)

        max_age = rule.get("max_age")
        if max_age is not None:
            age_match = re.search(r'(?:年龄[：:\s]*)?(\d+)\s*岁', candidate_text)
            if age_match and int(age_match.group(1)) > max_age:
                return False, 0, {"reason": f"年龄不符：要求≤{max_age}岁，实际{age_match.group(1)}岁"}

        work_location = rule.get("work_location")
        if work_location and work_location.strip():
            candidate_city = _extract_city(candidate_text)
            required_locations = re.split(r'[/、/]', work_location)
            required_locations = [loc.strip() for loc in required_locations if loc.strip()]
            if candidate_city and required_locations:
                if not any(loc in candidate_city for loc in required_locations):
                    return False, 0, {"reason": f"地点不符：要求{work_location}，期望{candidate_city}"}

        salary_max = rule.get("salary_max")
        if rule.get("salary_min") is not None and salary_max is not None:
            cand_min_k, _ = _parse_candidate_salary_range(candidate_text)
            if cand_min_k is not None and cand_min_k >= salary_max + 1:
                return False, 0, {"reason": f"薪资不匹配：岗位最高{salary_max}K，候选人期望最低{cand_min_k}K"}

        for condition in rule.get("required_conditions", []):
            cond_result = check_required_condition(candidate_text, condition)
            if not cond_result['passed']:
                return False, 0, {"reason": cond_result['reason']}
        details['required_conditions_matched'] = True

        tech_keywords_or = rule.get("tech_conditions", [])
        if tech_keywords_or:
            tech_found = any(tech.lower() in candidate_text.lower() for tech in tech_keywords_or)
            if not tech_found:
                return False, 0, {"reason": f"技术不匹配：需要{tech_keywords_or}中至少一项"}
        details['tech_matched'] = True

        keywords = rule.get("keywords", [])
        skill_score = 0
        total_possible_weight = 0
        matched_skills = []

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

            details['skill_matched_count'] = len(matched_skills)
            details['skill_matches'] = matched_skills
            details['skill_total'] = total_possible_weight

        if total_possible_weight > 0:
            skill_score_normalized = int((skill_score / total_possible_weight) * SCORE_SKILL_MAX)
        else:
            skill_score_normalized = SCORE_SKILL_MAX

        score = SCORE_BASE + skill_score_normalized + details['exp_bonus'] + details['edu_bonus']
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
            is_non_regular = any(ne in candidate_text for ne in NON_REGULAR_EDU)
            if has_regular_mark and has_bachelor and not is_non_regular:
                return {"passed": True, "reason": ""}
            if is_non_regular:
                return {"passed": False, "reason": f"必要条件不满足：{condition}（非统招）"}
            if has_bachelor:
                return {"passed": True, "reason": ""}
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}

        if condition not in candidate_text:
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}
        return {"passed": True, "reason": ""}

    elif isinstance(condition, dict):
        cond_type = condition.get("type", "or")
        items = condition.get("items", [])

        if not items:
            return {"passed": True, "reason": ""}

        if cond_type == "or":
            matched = any(item.lower() in candidate_text.lower() for item in items)
            if not matched:
                return {"passed": False, "reason": f"必要条件不满足：需要{items}中至少一项"}
            return {"passed": True, "reason": ""}

        elif cond_type == "and":
            for item in items:
                if item.lower() not in candidate_text.lower():
                    return {"passed": False, "reason": f"必要条件不满足：缺少{item}"}
            return {"passed": True, "reason": ""}

    return {"passed": True, "reason": ""}


def evaluate_candidate(candidate_text: str, rule: dict[str, Any]) -> bool:
    """兼容旧版本的布尔筛选接口。"""
    passed, score, details = filter_candidate(candidate_text, rule)
    return passed
