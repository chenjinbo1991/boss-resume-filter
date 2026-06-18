from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def test_runtime_import_dependencies_are_not_excluded_from_pyinstaller():
    """Keep import-time dependencies in the frozen app.

    DrissionPage imports sqlite3/DataRecorder and lxml.html during normal startup.
    Excluding any of these makes GUI actions fail inside the packaged EXE even
    when source-mode tests pass.
    """
    build_source = (BASE_DIR / "build.py").read_text(encoding="utf-8")
    forbidden_excludes = [
        "--exclude-module=sqlite3",
        "--exclude-module=lxml.html",
    ]

    for option in forbidden_excludes:
        assert option not in build_source


def test_pandas_is_not_a_packaging_dependency():
    """Excel export should stay on openpyxl to avoid bundling pandas and numpy."""
    requirements = (BASE_DIR / "requirements.txt").read_text(encoding="utf-8")
    build_source = (BASE_DIR / "build.py").read_text(encoding="utf-8")

    assert "pandas" not in requirements
    assert '"pandas": "pandas"' not in build_source
    assert "--exclude-module=numpy" in build_source
    assert "--exclude-module=numpy.libs" in build_source


def test_release_workflow_rebuilds_macos_when_dmg_is_missing():
    """macOS release completeness requires both the auto-update ZIP and installer DMG."""
    workflow = (BASE_DIR / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "BOSS_ResumeFilter_mac\\.zip" in workflow
    assert "BOSS_ResumeFilter\\.dmg" in workflow


def test_release_workflow_uploads_current_platform_directly_to_gitee():
    """The runner that built an artifact should upload it to Gitee without local relay."""
    workflow = (BASE_DIR / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "GITEE_TOKEN: ${{ secrets.GITEE_TOKEN }}" in workflow
    assert '--gitee-upload-local "$VERSION"' in workflow
