import sys

from bgs_papyrus.process import run_tool


def test_run_tool_captures_stdout():
    r = run_tool([sys.executable, "-c", "print(42)"], timeout=30)
    assert r.returncode == 0 and "42" in r.stdout


def test_run_tool_timeout_returns_negative():
    r = run_tool([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
    assert r.returncode == -1
