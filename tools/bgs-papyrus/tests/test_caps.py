import json
import subprocess
import sys


def test_capabilities_json_describes_supported_surface():
    result = subprocess.run(
        [sys.executable, "-m", "bgs_papyrus.cli", "capabilities", "--json"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    env = json.loads(result.stdout)
    assert "starfield" in env["data"]["games"]
    assert "ck" in env["data"]["backends"]["compile"]
    assert "sf-syntax-fix" in env["data"]["starfield_decompile"]
