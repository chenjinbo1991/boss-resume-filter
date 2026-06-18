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
