"""
Run the stable unit regression suite.

This entry point intentionally avoids browser automation, real BOSS pages,
network calls, and the user's live job_config.json.
"""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]
UNIT_DIR = Path(__file__).resolve().parent / "unit"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    test_files = sorted(UNIT_DIR.glob("test_*.py"))
    if not test_files:
        print("FAIL no unit test files found")
        return 1

    total = 0
    failures = 0

    for path in test_files:
        module = _load_module(path)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            fn = getattr(module, name)
            if not callable(fn):
                continue
            total += 1
            try:
                fn()
                print(f"PASS {path.name}::{name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {path.name}::{name}: {exc}")
            except Exception as exc:
                failures += 1
                print(f"ERROR {path.name}::{name}: {type(exc).__name__}: {exc}")

    print(f"SUMMARY total={total} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
