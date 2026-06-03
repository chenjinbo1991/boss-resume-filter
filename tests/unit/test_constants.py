"""constants 模块稳定性测试 — 防止评分阈值、城市列表等关键常量被意外修改。"""

from constants import (
    CHINESE_NUMERALS,
    MAJOR_CITIES,
    NON_REGULAR_EDU,
    SCORE_BASE,
    SCORE_EDU_MAX,
    SCORE_EXP_MAX,
    SCORE_SKILL_MAX,
    SCORE_THRESHOLD_PASS,
    SCORE_THRESHOLD_RECOMMEND,
    SCORE_THRESHOLD_STRONG,
)


# ========== 评分阈值排序 ==========

def test_score_thresholds_are_strictly_ascending():
    assert SCORE_THRESHOLD_PASS < SCORE_THRESHOLD_RECOMMEND < SCORE_THRESHOLD_STRONG


def test_score_components_sum_to_100():
    assert SCORE_BASE + SCORE_SKILL_MAX + SCORE_EXP_MAX + SCORE_EDU_MAX == 100


# ========== 中文数字映射 ==========

def test_chinese_numerals_has_all_basic_entries():
    expected_chars = {'零', '一', '二', '两', '三', '四', '五', '六', '七', '八', '九', '十'}
    assert expected_chars == set(CHINESE_NUMERALS.keys())


def test_chinese_numerals_values_are_correct():
    assert CHINESE_NUMERALS['零'] == 0
    assert CHINESE_NUMERALS['十'] == 10
    assert CHINESE_NUMERALS['两'] == 2  # 两 == 二


# ========== 非统招关键词 ==========

def test_non_regular_edu_contains_essential_keywords():
    essentials = ['自考', '成教', '函授', '专升本', '网络教育', '成人高考']
    for kw in essentials:
        assert kw in NON_REGULAR_EDU, f"缺少非统招关键词: {kw}"


# ========== 城市列表 ==========

def test_major_cities_sorted_by_length_descending():
    """城市列表按长度降序排列，确保 '哈尔滨' 优先于 '北京' 匹配。"""
    for i in range(len(MAJOR_CITIES) - 1):
        assert len(MAJOR_CITIES[i]) >= len(MAJOR_CITIES[i + 1]), \
            f"城市排序错误: '{MAJOR_CITIES[i]}' 应在 '{MAJOR_CITIES[i+1]}' 之前"


def test_major_cities_contains_key_cities():
    key_cities = ['北京', '上海', '广州', '深圳', '哈尔滨']
    for city in key_cities:
        assert city in MAJOR_CITIES, f"缺少关键城市: {city}"
