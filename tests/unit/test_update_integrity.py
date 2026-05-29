import contextlib
import io
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
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZboss-update")

        asset_info = {
            "size": path.stat().st_size,
            "sha256": updater._file_sha256(path),
        }

        ok, error = updater.verify_downloaded_file(path, asset_info)

    assert ok is True
    assert error is None


def test_verify_downloaded_file_rejects_size_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZboss-update")

        asset_info = {
            "size": path.stat().st_size + 1,
            "sha256": updater._file_sha256(path),
        }
        ok, error = updater.verify_downloaded_file(path, asset_info)

    assert ok is False
    assert "文件大小不匹配" in error


def test_verify_downloaded_file_rejects_sha256_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZboss-update")

        ok, error = updater.verify_downloaded_file(
            path,
            {"size": path.stat().st_size, "sha256": "0" * 64},
        )

    assert ok is False
    assert "SHA256 不匹配" in error


def test_verify_downloaded_file_rejects_missing_integrity_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZboss-update")

        ok, error = updater.verify_downloaded_file(path, {"size": path.stat().st_size})

    assert ok is False
    assert "缺少文件大小或 SHA256" in error


def test_verify_downloaded_file_rejects_invalid_exe_header():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"<html>not an exe</html>")

        asset_info = {
            "size": path.stat().st_size,
            "sha256": updater._file_sha256(path),
        }
        ok, error = updater.verify_downloaded_file(path, asset_info)

    assert ok is False
    assert "EXE 文件头无效" in error


def test_verify_downloaded_file_rejects_invalid_zip_header():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.zip"
        path.write_bytes(b"<html>not a zip</html>")

        asset_info = {
            "size": path.stat().st_size,
            "sha256": updater._file_sha256(path),
        }
        ok, error = updater.verify_downloaded_file(path, asset_info)

    assert ok is False
    assert "ZIP 文件头无效" in error


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


def test_update_latest_json_requires_complete_auto_update_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "BOSS_ResumeFilter.exe").write_bytes(b"exe")

        with _with_build_context(tmp_path, dist_dir, is_win=True, is_mac=False):
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    build.update_latest_json("9.9.9", "notes", quiet=True, require_complete_assets=True)
                except SystemExit as exc:
                    assert exc.code == 1
                else:
                    raise AssertionError("missing macos metadata should block latest.json publication")


def test_github_asset_matches_local_by_digest_without_download():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZsame-content")
        asset = {
            "size": path.stat().st_size,
            "digest": f"sha256:{build._sha256_file(path)}",
        }

        same, reason = build._github_asset_matches_local("v9.9.9", path, asset)

    assert same is True
    assert "SHA256 一致" in reason


def test_github_asset_size_mismatch_requires_upload():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZlocal")
        asset = {"size": path.stat().st_size + 1}

        same, reason = build._github_asset_matches_local("v9.9.9", path, asset)

    assert same is False
    assert "大小不一致" in reason


def test_gitee_asset_matches_local_downloads_remote_hash_when_digest_missing():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "asset.exe"
        path.write_bytes(b"MZsame-content")
        original_remote_hash = build._remote_file_sha256
        calls = []

        def fake_remote_hash(url, token=None):
            calls.append((url, token))
            return build._sha256_file(path)

        build._remote_file_sha256 = fake_remote_hash
        try:
            same, reason = build._gitee_asset_matches_local(
                path,
                {"size": path.stat().st_size},
                "owner",
                "repo",
                "v9.9.9",
                token="token",
            )
        finally:
            build._remote_file_sha256 = original_remote_hash

    assert same is True
    assert "SHA256 一致" in reason
    assert calls == [("https://gitee.com/owner/repo/releases/download/v9.9.9/asset.exe", "token")]


def test_current_platform_update_artifact_names_windows():
    original_is_mac = build.IS_MAC
    try:
        build.IS_MAC = False
        assert build._current_platform_update_artifact_names() == {"BOSS_ResumeFilter.exe"}
    finally:
        build.IS_MAC = original_is_mac


def test_current_platform_update_artifact_names_macos():
    original_is_mac = build.IS_MAC
    try:
        build.IS_MAC = True
        assert build._current_platform_update_artifact_names() == {
            "BOSS_ResumeFilter.dmg",
            "BOSS_ResumeFilter_mac.zip",
        }
    finally:
        build.IS_MAC = original_is_mac


def test_windows_update_script_resets_pyinstaller_runtime_env():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        current_exe = tmp_path / "BOSS_ResumeFilter.exe"
        new_exe = tmp_path / "download" / "BOSS_ResumeFilter.exe"
        new_exe.parent.mkdir()
        current_exe.write_bytes(b"old")
        new_exe.write_bytes(b"new")

        original_popen = updater.subprocess.Popen

        class FakeProcess:
            pass

        try:
            updater.subprocess.Popen = lambda *args, **kwargs: FakeProcess()
            ok, error = updater.update_windows(str(new_exe), str(current_exe))
        finally:
            updater.subprocess.Popen = original_popen

        bat_content = (tmp_path / "update.bat").read_text(encoding="utf-8")

    assert ok is True
    assert error is None
    assert 'set "PYINSTALLER_RESET_ENVIRONMENT=1"' in bat_content
    assert "set _PYI_" in bat_content
    assert "_MEI*" not in bat_content
