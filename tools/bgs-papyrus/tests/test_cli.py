import json
import os
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


def test_detect_toolchain_game_starfield_json_uses_env_root(tmp_path):
    root = tmp_path / "Starfield"
    compiler = root / "Tools" / "Papyrus Compiler" / "PapyrusCompiler.exe"
    compiler.parent.mkdir(parents=True)
    compiler.write_text("x")

    child_env = os.environ.copy()
    child_env["BGS_STARFIELD_PATH"] = str(root)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "bgs_papyrus.cli",
            "detect-toolchain",
            "--game",
            "starfield",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=child_env,
    )

    assert result.returncode == 0
    env = json.loads(result.stdout)
    assert env["ok"] is True
    assert env["data"]["per_game"]["starfield"]["ck_compiler"] == str(compiler)
