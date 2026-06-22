import queue
from pathlib import Path

import icons
from gui_main import BossFilterGUI, _optional_int_to_entry, _parse_optional_int_entry


def test_optional_max_age_none_displays_as_blank():
    assert _optional_int_to_entry(None) == ""


def test_optional_max_age_number_displays_as_number_text():
    assert _optional_int_to_entry(35) == "35"


def test_blank_max_age_saves_as_unlimited():
    assert _parse_optional_int_entry("", "最大年龄") is None
    assert _parse_optional_int_entry("   ", "最大年龄") is None


def test_invalid_max_age_is_rejected_with_field_name():
    try:
        _parse_optional_int_entry("None", "最大年龄")
    except ValueError as e:
        assert str(e) == "最大年龄必须为数字"
    else:
        raise AssertionError("invalid max age should raise ValueError")


def test_humanize_ai_parse_warning_replaces_internal_field_names():
    gui = BossFilterGUI.__new__(BossFilterGUI)

    text = gui._humanize_ai_parse_warning(
        "`keywords_add` 中的 Python weight 建议确认，required_conditions 里 OR 条件需要看一下"
    )

    assert "keywords" not in text
    assert "required_conditions" not in text
    assert "技能关键词" in text
    assert "权重" in text
    assert "必要条件" in text
    assert "满足任一项" in text


def test_candidate_detail_groups_api_resume_sections():
    gui = BossFilterGUI.__new__(BossFilterGUI)
    candidate = {
        "name": "张三",
        "job_name": "数据分析师",
        "geek_id": "g-api-detail",
        "match_score": 80,
        "skill_match_ratio": "3/3",
        "greet_sent": False,
        "summary": "\n".join([
            "期望薪资：15-20K",
            "年龄：29岁",
            "学历：本科",
            "经验：6年",
            "教育经历：南京大学 计算机科学 本科 2014 2018",
            "工作经历：某证券公司 数据分析师 2020 至今",
            "工作职责：负责 ETL 调度、SQL 指标开发和 Python 数据分析",
            "技能标签：Python、SQL、ETL",
        ]),
    }

    detail = gui._format_candidate_detail(candidate)

    assert "【教育经历】" in detail
    assert "南京大学 计算机科学 本科 2014 2018" in detail
    assert "【工作经历】" in detail
    assert "某证券公司 数据分析师 2020 至今" in detail
    assert "【工作职责】" in detail
    assert "负责 ETL 调度、SQL 指标开发和 Python 数据分析" in detail
    assert "【技能标签】" in detail
    assert "Python、SQL、ETL" in detail
    assert "【候选人摘要】" in detail


class _FakeRoot:
    def __init__(self, state="normal", width=1500, height=950):
        self._state = state
        self._width = width
        self._height = height

    def state(self):
        return self._state

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class _FakeTree:
    def __init__(self, width):
        self._width = width
        self.displaycolumns = "#all"
        self.column_options = {}

    def winfo_width(self):
        return self._width

    def cget(self, key):
        assert key == "displaycolumns"
        return self.displaycolumns

    def configure(self, **kwargs):
        self.displaycolumns = kwargs["displaycolumns"]

    def column(self, column, **kwargs):
        self.column_options[column] = kwargs


def test_result_tree_columns_expand_only_when_space_is_available():
    gui = BossFilterGUI.__new__(BossFilterGUI)
    gui.root = _FakeRoot()
    gui.result_tree = _FakeTree(1600)
    gui._update_result_tree_columns()
    assert len(gui.result_tree.displaycolumns) == 8

    gui.root = _FakeRoot(state="zoomed", width=1920, height=1040)
    gui.result_tree = _FakeTree(1400)
    gui._update_result_tree_columns()
    assert len(gui.result_tree.displaycolumns) == 11

    gui.result_tree = _FakeTree(1500)
    gui._update_result_tree_columns()
    assert len(gui.result_tree.displaycolumns) == 13
    assert gui.result_tree.displaycolumns[-2:] == ("school", "company")
    assert gui.result_tree.column_options["school"]["width"] > 150
    assert gui.result_tree.column_options["company"]["width"] > 170
    assert gui.result_tree.column_options["level"]["width"] < 110
    assert gui.result_tree.column_options["education"]["width"] == 140
    assert gui.result_tree.column_options["age"]["width"] == 110
    assert gui.result_tree.column_options["skills"]["width"] < 140
    assert gui.result_tree.column_options["name"]["stretch"] is False
    assert gui.result_tree.column_options["education"]["stretch"] is False
    assert gui.result_tree.column_options["skills"]["stretch"] is False
    assert gui.result_tree.column_options["school"]["stretch"] is False
    assert gui.result_tree.column_options["company"]["stretch"] is False
    assert sum(
        options["width"] for options in gui.result_tree.column_options.values()
    ) == 1498

    gui.root = _FakeRoot()
    gui.result_tree = _FakeTree(1500)
    gui._update_result_tree_columns()
    assert all(
        options["stretch"] is True
        for options in gui.result_tree.column_options.values()
    )
    assert gui.result_tree.column_options["skills"]["width"] == 85


def test_latest_history_value_uses_latest_end_date_not_list_order():
    entries = [
        {"school": "较早学校", "end": "2018.06"},
        {"school": "最近学校", "end": "2022.06"},
    ]

    value = BossFilterGUI._latest_history_value(entries, "school", "", "教育经历：")

    assert value == "最近学校"


def test_latest_history_value_treats_present_as_latest_and_falls_back_to_summary():
    works = [
        {"company": "上一家公司", "end": "2024.01"},
        {"company": "当前公司", "end": "至今"},
    ]
    assert BossFilterGUI._latest_history_value(
        works, "company", "", "工作经历："
    ) == "当前公司"

    assert BossFilterGUI._latest_history_value(
        [], "company", "工作经历：摘要公司 高级工程师 2022 至今", "工作经历："
    ) == "摘要公司"


def test_candidate_status_hides_internal_greet_context_capability():
    """状态栏只展示业务状态，不暴露打招呼上下文等内部实现。"""
    gui = BossFilterGUI.__new__(BossFilterGUI)
    candidate = {
        "greet_sent": False,
        "followup_status": "未沟通",
        "greet_context": {"chat_start": {"jid": "job-1", "lid": "list-1"}},
    }

    assert gui._format_candidate_status(candidate) == "未沟通"


def test_candidate_status_surfaces_pending_greeting_confirmation():
    gui = BossFilterGUI.__new__(BossFilterGUI)
    candidate = {
        "greet_sent": False,
        "followup_status": "未沟通",
        "greet_confirmation_pending": True,
    }

    assert gui._format_candidate_status(candidate) == "未沟通｜发送待确认"


def test_greet_confirmation_hint_explains_prepared_path_without_technical_terms():
    candidate = {
        "greet_context": {"chat_start": {"jid": "job-1", "lid": "list-1"}},
    }

    hint = BossFilterGUI._get_greet_confirmation_hint(candidate)

    assert "无需停留在原推荐页面" in hint
    assert "上下文" not in hint
    assert "API" not in hint


def test_greet_confirmation_hint_explains_current_page_fallback():
    hint = BossFilterGUI._get_greet_confirmation_hint({})

    assert "当前推荐页面定位" in hint
    assert "该岗位的推荐牛人页面" in hint


def test_update_log_waits_until_lazy_run_page_creates_log_widget():
    """未进入运行控制页时保留日志，不能因 log_text 尚未创建而报错或丢消息。"""
    class FakeRoot:
        def __init__(self):
            self.scheduled = []

        def after(self, delay, callback):
            self.scheduled.append((delay, callback))

    gui = BossFilterGUI.__new__(BossFilterGUI)
    gui.root = FakeRoot()
    gui.log_queue = queue.Queue()
    gui.log_queue.put("打招呼成功")

    gui.update_log()

    assert gui.log_queue.qsize() == 1
    assert gui.root.scheduled == [(100, gui.update_log)]


def test_browser_auto_check_debounces_one_transient_navigation_miss():
    gui = BossFilterGUI.__new__(BossFilterGUI)
    gui._browser_non_target_checks = 0

    assert gui._should_defer_browser_navigation_warning(silent=True) is True
    assert gui._should_defer_browser_navigation_warning(silent=True) is False


def test_browser_auto_check_debounces_one_transient_connection_failure():
    gui = BossFilterGUI.__new__(BossFilterGUI)
    gui._browser_connection_failures = 0

    assert gui._should_defer_browser_connection_failure(silent=True) is True
    assert gui._should_defer_browser_connection_failure(silent=True) is False
    assert gui._should_defer_browser_connection_failure(silent=False) is False


def test_result_page_stats_show_greeted_after_pending():
    """结果页依次展示强烈推荐、推荐、待定、已打招呼。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    stats_block = source[source.index("stats_data = [", source.index("def create_result_page")):]
    stats_block = stats_block[:stats_block.index("\n\n        for icon_name")]

    assert '"通过筛选"' not in stats_block
    assert (
        stats_block.index('"强烈推荐"')
        < stats_block.index('"推荐"')
        < stats_block.index('"待定"')
        < stats_block.index('"已打招呼"')
    )
    assert '"strong_recommend"' in stats_block
    assert '"hourglass"' in stats_block
    assert '"pending"' in stats_block
    assert '("chat", "已打招呼", "greeted"' in stats_block


def test_result_page_greeted_detail_uses_passed_candidates_only():
    """已打招呼指标只统计通过筛选且已打招呼的候选人。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    detail_block = source[source.index("elif stat_type == 'greeted':"):]
    detail_block = detail_block[:detail_block.index("\n            else:")]

    assert "SCORE_THRESHOLD_PASS" in detail_block
    assert "c.get('greet_sent', False)" in detail_block


def test_passed_filter_uses_enlarged_original_people_icon():
    """通过筛选沿用原双人图案，并适当放大视觉占位。"""
    assert "passed_filter" in icons.ICON_REGISTRY
    original = icons.ICON_REGISTRY["people"](40, "white", (0, 0, 0, 0), 3)
    image = icons.ICON_REGISTRY["passed_filter"](40, "white", (0, 0, 0, 0), 3)
    assert image.size == (40, 40)
    assert image.getbbox() is not None
    original_width = original.getbbox()[2] - original.getbbox()[0]
    enlarged_width = image.getbbox()[2] - image.getbbox()[0]
    assert enlarged_width > original_width
    assert enlarged_width >= 36


def test_strong_recommendation_uses_registered_emphasized_thumb_icon():
    """强烈推荐使用点赞加光芒，与普通推荐保持同一视觉语言。"""
    assert "strong_recommend" in icons.ICON_REGISTRY
    image = icons.ICON_REGISTRY["strong_recommend"](40, "white", (0, 0, 0, 0), 3)
    assert image.size == (40, 40)
    assert image.getbbox() is not None
    assert image.getbbox()[2] - image.getbbox()[0] >= 32
    assert image.getbbox()[3] - image.getbbox()[1] >= 36


def test_home_page_strong_recommendation_uses_emphasized_thumb_icon():
    """首页与筛选结果页统一使用点赞加光芒表达强烈推荐。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    home_block = source[source.index("cards_data = [", source.index("def create_home_page")):]
    home_block = home_block[:home_block.index("\n\n        self.home_stats_vars")]

    assert '("strong_recommend", "强烈推荐"' in home_block
    assert '("star", "强烈推荐"' not in home_block


def test_home_page_renames_total_candidates_to_passed_filter():
    """首页第一张卡片展示通过筛选，并使用放大的原双人图案。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    home_block = source[source.index("cards_data = [", source.index("def create_home_page")):]
    home_block = home_block[:home_block.index("\n\n        self.home_stats_vars")]

    assert '("passed_filter", "通过筛选", "total_home"' in home_block
    assert '"累计候选人"' not in home_block


def test_stats_page_strong_recommendation_uses_emphasized_thumb_icon():
    """数据统计页与其他页面统一使用点赞加光芒表达强烈推荐。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    stats_block = source[source.index("summary_items = [", source.index("def create_stats_page")):]
    stats_block = stats_block[:stats_block.index("\n\n        for icon_name")]

    assert '("strong_recommend", "强烈推荐"' in stats_block
    assert '("star", "强烈推荐"' not in stats_block


def test_stats_page_renames_total_candidates_to_passed_filter():
    """数据统计页第一张卡片展示通过筛选，并使用放大的原双人图案。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    stats_block = source[source.index("summary_items = [", source.index("def create_stats_page")):]
    stats_block = stats_block[:stats_block.index("\n\n        for icon_name")]

    assert '("passed_filter", "通过筛选", "total"' in stats_block
    assert '"总候选人"' not in stats_block


def test_stats_page_greeted_uses_chat_icon_consistently():
    """数据统计页与首页、筛选结果页统一使用聊天气泡表示已打招呼。"""
    source = Path("gui_main.py").read_text(encoding="utf-8")
    stats_block = source[source.index("summary_items = [", source.index("def create_stats_page")):]
    stats_block = stats_block[:stats_block.index("\n\n        for icon_name")]

    assert '("chat", "已打招呼", "greeted"' in stats_block
    assert '("mail", "已打招呼", "greeted"' not in stats_block
