import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import updater


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_get_cached_release_notes_returns_fresh_current_version():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache = tmp_path / "release_notes_cache.json"
        cache.write_text(
            json.dumps({
                "version": "2.11.2",
                "fetched_at": 990,
                "release_notes": "### 新增功能\n\n- 远端说明",
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        with patch.object(updater.time, "time", return_value=1000):
            notes = updater.get_cached_release_notes("v2.11.2", base_dir=tmp_path)

        assert "远端说明" in notes


def test_fetch_current_release_notes_uses_gitee_latest_json():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({
            "version": "2.11.2",
            "release_notes": "### 新增功能\n\n- 当前版本远端说明",
        })

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with patch.object(updater.requests, "get", side_effect=fake_get):
            notes = updater.fetch_current_release_notes("2.11.2", use_cache=False, base_dir=tmp_path)

        assert "当前版本远端说明" in notes
        assert len(calls) == 1
        assert calls[0][1]["timeout"] == updater.UPDATE_TIMEOUT_RELEASE_NOTES_GITEE
        cached = json.loads((tmp_path / "release_notes_cache.json").read_text(encoding="utf-8"))
        assert cached["source"] == "gitee"


def test_fetch_current_release_notes_retries_gitee_before_github():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            raise updater.requests.exceptions.Timeout("slow")
        return FakeResponse({
            "version": "2.11.2",
            "release_notes": "### 体验优化\n\n- Gitee 重试成功",
        })

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with patch.object(updater.requests, "get", side_effect=fake_get):
            notes = updater.fetch_current_release_notes("2.11.2", use_cache=False, base_dir=tmp_path)

        assert "Gitee 重试成功" in notes
        assert len(calls) == 2
        assert "gitee.com" in calls[0][0]
        assert "gitee.com" in calls[1][0]
        assert calls[0][1]["timeout"] == updater.UPDATE_TIMEOUT_RELEASE_NOTES_GITEE
        assert calls[1][1]["timeout"] == updater.UPDATE_TIMEOUT_RELEASE_NOTES_GITEE_RETRY


def test_fetch_current_release_notes_falls_back_to_github_tag():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if "gitee.com" in url and len(calls) <= 2:
            raise updater.requests.exceptions.Timeout("slow")
        return FakeResponse({"body": "### 问题修复\n\n- GitHub 说明"})

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with patch.object(updater.requests, "get", side_effect=fake_get):
            notes = updater.fetch_current_release_notes("2.11.2", use_cache=False, base_dir=tmp_path)

        assert "GitHub 说明" in notes
        assert len(calls) == 3
        assert calls[2][0].endswith("/releases/tags/v2.11.2")
        assert calls[2][1]["timeout"] == updater.UPDATE_TIMEOUT_RELEASE_NOTES_GITHUB
