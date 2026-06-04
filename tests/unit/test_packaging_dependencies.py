from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def test_runtime_import_dependencies_are_not_excluded_from_pyinstaller():
    """Keep import-time dependencies in the frozen app.

    DrissionPage imports sqlite3/DataRecorder and lxml.html during normal startup.
    pandas imports numpy during startup. Excluding any of these makes GUI actions
    fail inside the packaged EXE even when source-mode tests pass.
    """
    build_source = (BASE_DIR / "build.py").read_text(encoding="utf-8")
    forbidden_excludes = [
        "--exclude-module=sqlite3",
        "--exclude-module=numpy",
        "--exclude-module=numpy.libs",
        "--exclude-module=lxml.html",
    ]

    for option in forbidden_excludes:
        assert option not in build_source
