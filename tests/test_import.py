"""Smoke test for importing bossmaster.py without running the CLI."""
from pathlib import Path

print("Start bossmaster.py import smoke test...")

try:
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("bossmaster", root / "bossmaster.py")
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
        print("PASS module import succeeded")
    except Exception as e:
        print(f"FAIL module import failed: {e}")
        import traceback
        traceback.print_exc()

except ImportError as e:
    print(f"FAIL import error: {e}")
    import traceback
    traceback.print_exc()

print("Import smoke test finished")
