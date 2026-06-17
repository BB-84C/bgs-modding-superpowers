"""Subprocess-level stdio encoding regression tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_sidecar_round_trips_utf8_json_when_windows_stdio_default_is_cp950(tmp_path):
    """TS writes UTF-8 JSON; sidecar must not decode it through the ANSI code page."""
    src_dir = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    # Reproduce the WL2 mojibake class: UTF-8 bytes for 自用 decoded as CP950
    # become 鑷?鐢?.  The sidecar entrypoint must force UTF-8 regardless of the
    # inherited Windows console/stdio default.
    env["PYTHONIOENCODING"] = "cp950:replace"
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "system.echo",
        "params": {"profile": "BB84自用"},
    }

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mo2_mcp_sidecar",
            "--mods-root",
            str(tmp_path / "mods"),
            "--game",
            "FALLOUT4",
        ],
        input=json.dumps(request, ensure_ascii=False) + "\n",
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=10,
    )

    assert proc.returncode == 0, proc.stderr
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line]
    assert lines[0] == {"ready": True}
    assert lines[1]["result"]["profile"] == "BB84自用"
