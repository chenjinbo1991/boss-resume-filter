import json
import tempfile
from pathlib import Path

import build
import updater


def test_verify_downloaded_file_accepts_matching_size_and_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.bin"
        path.write_bytes(b"boss-update")

        asset_info = {
            "size": path.stat().st_size,
            "sha256": updater._file_sha256(path),
        }

        ok, error = updater.verify_downloaded_file(path, asset_info)

    assert ok is True
    assert error is None


def test_verify_downloaded_file_rejects_size_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.bin"
        path.write_bytes(b"boss-update")

        ok, error = updater.verify_downloaded_file(path, {"size": path.stat().st_size + 1})

    assert ok is False
    assert "文件大小不匹配" in error


def test_verify_downloaded_file_rejects_sha256_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.bin"
        path.write_bytes(b"boss-update")

        ok, error = updater.verify_downloaded_file(path, {"sha256": "0" * 64})

    assert ok is False
    assert "SHA256 不匹配" in error


def test_update_latest_json_writes_asset_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "BOSS_ResumeFilter.exe").write_bytes(b"exe")
        (dist_dir / "README.md").write_text("readme", encoding="utf-8")

        original_base_dir = build.BASE_DIR
        original_dist_dir = build.DIST_DIR
        original_is_win = build.IS_WIN
        original_is_mac = build.IS_MAC
        try:
            build.BASE_DIR = tmp_path
            build.DIST_DIR = dist_dir
            build.IS_WIN = True
            build.IS_MAC = False
            build.update_latest_json("9.9.9", "notes")

            data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
            expected_exe_sha256 = build._sha256_file(dist_dir / "BOSS_ResumeFilter.exe")
        finally:
            build.BASE_DIR = original_base_dir
            build.DIST_DIR = original_dist_dir
            build.IS_WIN = original_is_win
            build.IS_MAC = original_is_mac

    assert data["assets"]["windows"]["size"] == 3
    assert data["assets"]["windows"]["sha256"] == expected_exe_sha256
    assert "readme" not in data["assets"]
