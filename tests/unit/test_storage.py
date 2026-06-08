"""storage 模块单元测试 — 覆盖去重、打招呼状态合并、原子写入、备份恢复、
get_greeted_geek_ids、is_already_greeted、build_greeted_index。"""

import contextlib
import io
import json
import os
import tempfile

from storage import (
    _dedupe_candidates,
    build_greeted_index,
    get_greeted_geek_ids,
    is_already_greeted,
    load_candidates_all,
    save_candidates_all,
)


# ========== _dedupe_candidates ==========

def test_dedupe_keeps_higher_score():
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 60},
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 80


def test_dedupe_different_job_names_not_merged():
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 70},
        {"geek_id": "g1", "job_name": "Python", "match_score": 60},
    ])
    assert len(result) == 2


def test_dedupe_merges_greet_sent_from_old_to_new():
    """old 有 greet_sent=True，new 没有 → 合并后保留 True。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 70, "greet_sent": True},
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
    ])
    assert len(result) == 1
    assert result[0]["greet_sent"] is True
    assert result[0]["match_score"] == 80


def test_dedupe_preserves_feedback_from_old_to_new():
    """高分新记录替换旧记录时，保留旧记录上的人工反馈。"""
    result = _dedupe_candidates([
        {
            "geek_id": "g1",
            "job_name": "Java",
            "match_score": 70,
            "feedback_status": "误推",
            "feedback_note": "项目深度不足",
            "feedback_updated_at": "20260608_100000",
        },
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 80
    assert result[0]["feedback_status"] == "误推"
    assert result[0]["feedback_note"] == "项目深度不足"


def test_dedupe_preserves_feedback_from_new_to_old():
    """低分新记录不替换旧记录时，也要把新记录上的人工反馈合并回旧记录。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
        {
            "geek_id": "g1",
            "job_name": "Java",
            "match_score": 70,
            "feedback_status": "合适",
            "feedback_note": "可约面",
            "feedback_updated_at": "20260608_110000",
        },
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 80
    assert result[0]["feedback_status"] == "合适"
    assert result[0]["feedback_note"] == "可约面"


def test_dedupe_preserves_followup_from_old_to_new():
    """高分新记录替换旧记录时，保留旧记录上的跟进状态。"""
    result = _dedupe_candidates([
        {
            "geek_id": "g1",
            "job_name": "Java",
            "match_score": 70,
            "followup_status": "已回复",
            "followup_note": "等候选人确认时间",
            "followup_updated_at": "20260608_120000",
        },
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 80
    assert result[0]["followup_status"] == "已回复"
    assert result[0]["followup_note"] == "等候选人确认时间"


def test_dedupe_preserves_followup_from_new_to_old():
    """低分新记录不替换旧记录时，也要把新记录上的跟进状态合并回旧记录。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
        {
            "geek_id": "g1",
            "job_name": "Java",
            "match_score": 70,
            "followup_status": "待约面",
            "followup_note": "周三沟通",
            "followup_updated_at": "20260608_130000",
        },
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 80
    assert result[0]["followup_status"] == "待约面"
    assert result[0]["followup_note"] == "周三沟通"


def test_dedupe_merges_greet_sent_from_new_to_old():
    """new 有 greet_sent=True → 直接替换。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 80},
        {"geek_id": "g1", "job_name": "Java", "match_score": 70, "greet_sent": True},
    ])
    assert len(result) == 1
    assert result[0]["greet_sent"] is True


def test_dedupe_clears_greeting_in_progress_when_greeted():
    """greeting_in_progress + greet_sent → 清除 greeting_in_progress。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 70,
         "greet_sent": True, "greeting_in_progress": True},
    ])
    assert len(result) == 1
    assert result[0]["greet_sent"] is True
    assert "greeting_in_progress" not in result[0]


def test_dedupe_keeps_greeting_in_progress_when_not_greeted():
    """只有 greeting_in_progress、没有 greet_sent → 保留。"""
    result = _dedupe_candidates([
        {"geek_id": "g1", "job_name": "Java", "match_score": 70,
         "greeting_in_progress": True},
    ])
    assert len(result) == 1
    assert result[0]["greeting_in_progress"] is True


def test_dedupe_no_geek_id_skipped():
    """没有 geek_id 的记录不参与去重（被丢弃）。"""
    result = _dedupe_candidates([
        {"job_name": "Java", "match_score": 70},
        {"geek_id": "g1", "job_name": "Java", "match_score": 60},
    ])
    assert len(result) == 1
    assert result[0]["geek_id"] == "g1"


def test_dedupe_empty_job_name_defaults_to_empty_string():
    result = _dedupe_candidates([
        {"geek_id": "g1", "match_score": 60},
        {"geek_id": "g1", "match_score": 70},
    ])
    assert len(result) == 1
    assert result[0]["match_score"] == 70


def test_dedupe_empty_list():
    assert _dedupe_candidates([]) == []


# ========== get_greeted_geek_ids ==========

def test_get_greeted_geek_ids_extracts_greeted():
    candidates = [
        {"geek_id": "g1", "greet_sent": True},
        {"geek_id": "g2", "greet_sent": False},
        {"geek_id": "g3", "greet_sent": True},
        {"geek_id": "g4"},
    ]
    assert get_greeted_geek_ids(candidates) == {"g1", "g3"}


def test_get_greeted_geek_ids_empty():
    assert get_greeted_geek_ids([]) == set()


# ========== is_already_greeted ==========

def test_is_already_greeted_by_geek_id_and_job():
    candidates = [
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
        {"geek_id": "g1", "job_name": "Python", "greet_sent": False},
    ]
    assert is_already_greeted(candidates, "g1", "Java") is True
    assert is_already_greeted(candidates, "g1", "Python") is False
    assert is_already_greeted(candidates, "g2", "Java") is False


def test_is_already_greeted_without_job_name():
    """无 job_name 时，只要该 geek_id 在任何岗位打过招呼即返回 True。"""
    candidates = [
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
    ]
    assert is_already_greeted(candidates, "g1") is True
    assert is_already_greeted(candidates, "g2") is False


def test_is_already_greeted_with_index():
    candidates = [
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
        {"geek_id": "g2", "job_name": "Python", "greet_sent": False},
    ]
    index = build_greeted_index(candidates)
    assert is_already_greeted(candidates, "g1", "Java", index) is True
    assert is_already_greeted(candidates, "g2", "Python", index) is False


def test_is_already_greeted_index_without_job_name():
    candidates = [
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
    ]
    index = build_greeted_index(candidates)
    assert is_already_greeted(candidates, "g1", greeted_index=index) is True
    assert is_already_greeted(candidates, "g9", greeted_index=index) is False


# ========== build_greeted_index ==========

def test_build_greeted_index_only_greeted():
    candidates = [
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
        {"geek_id": "g2", "job_name": "Python", "greet_sent": False},
        {"geek_id": "g3", "job_name": "Go", "greet_sent": True},
    ]
    index = build_greeted_index(candidates)
    assert ("g1", "Java") in index
    assert ("g3", "Go") in index
    assert ("g2", "Python") not in index


def test_build_greeted_index_skips_no_geek_id():
    candidates = [
        {"job_name": "Java", "greet_sent": True},
        {"geek_id": "g1", "job_name": "Java", "greet_sent": True},
    ]
    index = build_greeted_index(candidates)
    assert len(index) == 1
    assert ("g1", "Java") in index


# ========== save_candidates_all 原子写入 ==========

def test_save_creates_backup_of_existing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        # 先写入初始数据
        with open(target, "w", encoding="utf-8") as f:
            json.dump([{"geek_id": "old", "job_name": "Java"}], f)

        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all([
                {"geek_id": "g1", "job_name": "Java", "match_score": 70},
            ], target)

        # 备份文件应存在且包含旧数据
        bak = target + ".bak"
        assert os.path.exists(bak)
        with open(bak, "r", encoding="utf-8") as f:
            backup = json.load(f)
        assert backup[0]["geek_id"] == "old"


def test_save_no_tmp_file_left_behind():
    """原子写入完成后 .tmp 文件不应残留。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all([
                {"geek_id": "g1", "job_name": "Java", "match_score": 70},
            ], target)
        tmp = target + ".tmp"
        assert not os.path.exists(tmp)


def test_save_no_backup_when_no_existing_file():
    """首次保存（无现有文件）不应产生 .bak。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all([
                {"geek_id": "g1", "job_name": "Java", "match_score": 70},
            ], target)
        bak = target + ".bak"
        assert not os.path.exists(bak)


# ========== load_candidates_all ==========

def test_load_returns_empty_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        with contextlib.redirect_stdout(io.StringIO()):
            result = load_candidates_all(target)
    assert result == []


def test_load_returns_empty_when_both_files_corrupt():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        with open(target, "w") as f:
            f.write("{broken")
        with open(target + ".bak", "w") as f:
            f.write("also{broken")
        with contextlib.redirect_stdout(io.StringIO()):
            result = load_candidates_all(target)
    assert result == []


def test_load_restores_backup_and_copies_to_main():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        backup_data = [{"geek_id": "g1", "job_name": "Java"}]
        with open(target, "w") as f:
            f.write("{broken")
        with open(target + ".bak", "w", encoding="utf-8") as f:
            json.dump(backup_data, f)

        with contextlib.redirect_stdout(io.StringIO()):
            result = load_candidates_all(target)

        assert result == backup_data
        # 恢复后备份应被复制到主文件
        with open(target, "r", encoding="utf-8") as f:
            restored = json.load(f)
        assert restored == backup_data


# ========== save + load 集成 ==========

def test_save_then_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        data = [
            {"geek_id": "g1", "job_name": "Java", "match_score": 80, "greet_sent": True},
            {"geek_id": "g2", "job_name": "Python", "match_score": 65},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all(data, target)
            loaded = load_candidates_all(target)
    assert len(loaded) == 2
    assert loaded[0]["greet_sent"] is True


# ========== load_candidates_all 边界场景 ==========

def test_load_happy_path_from_valid_file():
    """主文件正常时应直接加载，不触发备份恢复。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        data = [{"geek_id": "g1", "job_name": "Java", "match_score": 70}]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_candidates_all(target)
    assert len(result) == 1
    assert result[0]["geek_id"] == "g1"


def test_load_backup_corrupted_returns_empty():
    """主文件损坏且备份也损坏时应返回空列表。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        with open(target, "w") as f:
            f.write("{broken")
        with open(target + ".bak", "w") as f:
            f.write("also{broken")
        with contextlib.redirect_stdout(io.StringIO()):
            result = load_candidates_all(target)
    assert result == []


# ========== save_candidates_all 边界场景 ==========

def test_save_backup_failure_still_saves():
    """备份创建失败时，保存操作本身不应中断。"""
    import unittest.mock as mock
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "candidates_all.json")
        # 先创建一个文件，这样 save 会尝试备份
        with open(target, "w", encoding="utf-8") as f:
            json.dump([{"geek_id": "old"}], f)

        with mock.patch('storage.shutil.copy2', side_effect=OSError("disk full")):
            with contextlib.redirect_stdout(io.StringIO()):
                save_candidates_all([
                    {"geek_id": "g1", "job_name": "Java", "match_score": 70},
                ], target)

        # 数据应仍然保存成功
        with open(target, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert len(saved) == 1
        assert saved[0]["geek_id"] == "g1"


def test_save_with_explicit_path_creates_backup():
    """显式路径保存时，备份也应在同一目录下。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "nested", "candidates.json")
        os.makedirs(os.path.dirname(target))
        # 先写入旧数据
        with open(target, "w", encoding="utf-8") as f:
            json.dump([{"geek_id": "old"}], f)

        with contextlib.redirect_stdout(io.StringIO()):
            save_candidates_all([
                {"geek_id": "g1", "job_name": "Java", "match_score": 70},
            ], target)

        bak = target + ".bak"
        assert os.path.exists(bak)
        with open(bak, "r", encoding="utf-8") as f:
            backup = json.load(f)
        assert backup[0]["geek_id"] == "old"
