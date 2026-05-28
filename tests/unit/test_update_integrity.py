import json
import tempfile
from pathlib import Path

import build
import updater


def _with_build_context(tmp_path, dist_dir, *, is_win, is_mac):
    class BuildContext:
        def __enter__(self):
            self.original_base_dir = build.BASE_DIR
            self.original_dist_dir = build.DIST_DIR
            self.original_is_win = build.IS_WIN
            self.original_is_mac = build.IS_MAC
            build.BASE_DIR = tmp_path
            build.DIST_DIR = dist_dir
            build.IS_WIN = is_win
            build.IS_MAC = is_mac

        def __exit__(self, exc_type, exc, tb):
            build.BASE_DIR = self.original_base_dir
            build.DIST_DIR = self.original_dist_dir
            build.IS_WIN = self.original_is_win
            build.IS_MAC = self.original_is_mac

    return BuildContext()


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

        with _with_build_context(tmp_path, dist_dir, is_win=True, is_mac=False):
            build.update_latest_json("9.9.9", "notes", quiet=True)

            data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
            expected_exe_sha256 = build._sha256_file(dist_dir / "BOSS_ResumeFilter.exe")

    assert data["assets"]["windows"]["size"] == 3
    assert data["assets"]["windows"]["sha256"] == expected_exe_sha256
    assert "readme" not in data["assets"]


def test_update_latest_json_writes_macos_update_asset_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        zip_path = dist_dir / "BOSS_ResumeFilter_mac.zip"
        dmg_path = dist_dir / "BOSS_ResumeFilter.dmg"
        zip_path.write_bytes(b"zip")
        dmg_path.write_bytes(b"dmg")

        with _with_build_context(tmp_path, dist_dir, is_win=False, is_mac=True):
            build.update_latest_json("9.9.9", "notes", quiet=True)

            data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
            expected_zip_sha256 = build._sha256_file(zip_path)
            expected_dmg_sha256 = build._sha256_file(dmg_path)

    assert data["assets"]["macos"]["size"] == 3
    assert data["assets"]["macos"]["sha256"] == expected_zip_sha256
    assert data["assets"]["macos_dmg"]["size"] == 3
    assert data["assets"]["macos_dmg"]["sha256"] == expected_dmg_sha256


def test_latest_json_manifest_keeps_download_and_asset_keys_consistent():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "BOSS_ResumeFilter_mac.zip").write_bytes(b"zip")
        (dist_dir / "BOSS_ResumeFilter.dmg").write_bytes(b"dmg")

        downloads_cn = {
            "macos": "https://gitee.example/BOSS_ResumeFilter_mac.zip",
            "macos_dmg": "https://gitee.example/BOSS_ResumeFilter.dmg",
        }
        with _with_build_context(tmp_path, dist_dir, is_win=False, is_mac=True):
            build.update_latest_json("9.9.9", "notes", downloads_cn=downloads_cn, quiet=True)
            data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))

    update_asset_keys = {"windows", "macos", "macos_dmg"}
    assert set(data["downloads"]) >= update_asset_keys
    assert set(data["downloads_cn"]) <= set(data["downloads"])
    assert set(data["assets"]) <= update_asset_keys
    assert set(data["assets"]) <= set(data["downloads"])
