import json
import subprocess
import sys


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "bgs_papyrus.cli", *args],
        capture_output=True,
        text=True,
    )


def test_capabilities_json_envelope():
    r = run("capabilities", "--json")
    assert r.returncode == 0
    env = json.loads(r.stdout)
    assert env["ok"] is True and env["tool"] == "bgs-papyrus"
