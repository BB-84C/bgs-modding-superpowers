r"""Gated E2E smoke test against a real running MO2 instance.

Skipped unless MO2_HARNESS=1 is set. Requires:
- MO2 running at $BGS_MO2_ROOT (defaults to D:\awesome-bgs-mod-master\.artifacts\mo2)
- mo2_agent_control plugin loaded + endpoint.json published
- PowerShell 7+ for NamedPipeClientStream

Run from project root:
    $env:MO2_HARNESS = "1"
    $env:BGS_MO2_ROOT = "D:\awesome-bgs-mod-master\.artifacts\mo2"
    # Start MO2 manually first
    pytest tools/mo2-control-plane/live-bridge/tests/test_broker_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("MO2_HARNESS") != "1",
    reason="Requires running MO2 instance; set MO2_HARNESS=1 to enable",
)

MO2_ROOT = Path(os.environ.get("BGS_MO2_ROOT", r"D:\awesome-bgs-mod-master\.artifacts\mo2"))
ENDPOINT_FILE = MO2_ROOT / "plugins" / "Mo2AgentControl" / "bootstrap" / "runtime" / "endpoint.json"


def _read_endpoint() -> str:
    """Read the live broker pipe name from endpoint.json."""

    if not ENDPOINT_FILE.exists():
        raise RuntimeError(
            f"endpoint.json not found at {ENDPOINT_FILE}; "
            "is MO2 running with the Mo2AgentControl plugin loaded?",
        )
    info = json.loads(ENDPOINT_FILE.read_text(encoding="utf-8"))
    return info["endpoint"]


def _send_pipe(method: str, payload: dict, timeout_s: int = 30) -> dict:
    """Send a single JSON-RPC request via PowerShell NamedPipeClientStream."""

    pipe_name = _read_endpoint()
    request = {
        "protocol_version": "1",
        "request_id": f"smoke-{int(time.time() * 1000)}",
        "session_id": "smoke-test",
        "method": method,
        "payload": payload,
    }
    request_json = json.dumps(request).replace("'", "''")

    script = f"""
$ErrorActionPreference = 'Stop'
try {{
    $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', '{pipe_name}', 'InOut')
    $pipe.Connect({timeout_s * 1000})
    $writer = New-Object System.IO.StreamWriter($pipe)
    $writer.AutoFlush = $true
    $reader = New-Object System.IO.StreamReader($pipe)
    $writer.WriteLine('{request_json}')
    $response = $reader.ReadLine()
    Write-Output $response
    $pipe.Dispose()
}} catch {{
    Write-Error "pipe error: $_"
    exit 1
}}
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout_s + 5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pipe call failed: {result.stderr}")
    response_line = result.stdout.strip()
    if not response_line:
        raise RuntimeError(f"empty pipe response; stderr: {result.stderr}")
    return json.loads(response_line)


def test_smoke_system_ping():
    """Sanity: broker responds to system.ping."""

    resp = _send_pipe("system.ping", {})
    assert resp["ok"] is True


def test_smoke_mods_list_returns_real_mods():
    """Real mods.list against the FO4 harness profile."""

    resp = _send_pipe("mods.list", {})
    assert resp["ok"] is True
    mods = resp["result"]["mods"]
    assert isinstance(mods, list)
    assert len(mods) >= 3, f"expected >=3 mods in dev harness, got {len(mods)}"


def test_smoke_plugins_list_returns_fallout4_esm():
    """Real plugins.list: Fallout4.esm must appear (FO4 master)."""

    resp = _send_pipe("plugins.list", {})
    assert resp["ok"] is True
    names = [plugin["name"] for plugin in resp["result"]["plugins"]]
    assert "Fallout4.esm" in names


def test_smoke_profile_active_matches_expected():
    """The dev harness uses the Default profile."""

    resp = _send_pipe("profile.active", {})
    assert resp["ok"] is True
    assert resp["result"]["name"] == "Default"


def test_smoke_profile_list_returns_default():
    """profile.list enumerates at least the Default profile dir."""

    resp = _send_pipe("profile.list", {})
    assert resp["ok"] is True
    names = [profile["name"] for profile in resp["result"]["profiles"]]
    assert "Default" in names


def test_smoke_executables_list_includes_opencode_xedit():
    """The harness has OpenCode xEdit Automation Serve configured per AGENTS.md."""

    resp = _send_pipe("executables.list", {})
    assert resp["ok"] is True
    titles = [executable["title"] for executable in resp["result"]["executables"]]
    assert any("OpenCode" in title and "xEdit" in title for title in titles), (
        f"expected OpenCode xEdit Automation Serve in executables; got {titles}"
    )


def test_smoke_system_capabilities():
    """system.capabilities returns the registered command surface."""

    resp = _send_pipe("system.capabilities", {})
    assert resp["ok"] is True
    assert "commands" in resp["result"] or "capabilities" in resp["result"]
