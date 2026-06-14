"""Skeleton smoke test for Task 23.

Verifies sidecar invokable, emits ready signal, handles system.echo + method-not-found.
"""
import json
import subprocess
import sys


def test_sidecar_emits_ready_signal_and_echoes(tmp_path):
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "mo2_mcp_sidecar",
         "--mods-root", str(mods_dir), "--game", "FALLOUT4"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    try:
        ready_line = proc.stdout.readline()
        assert json.loads(ready_line) == {"ready": True}

        req = json.dumps({"jsonrpc": "2.0", "id": 1,
                          "method": "system.echo", "params": {"hello": "world"}}) + "\n"
        proc.stdin.write(req); proc.stdin.flush()
        resp = json.loads(proc.stdout.readline())
        assert resp["result"] == {"hello": "world"}
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


def test_unknown_method_returns_error(tmp_path):
    mods_dir = tmp_path / "mods"; mods_dir.mkdir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "mo2_mcp_sidecar",
         "--mods-root", str(mods_dir), "--game", "FALLOUT4"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    try:
        proc.stdout.readline()  # discard ready
        req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "nonexistent"}) + "\n"
        proc.stdin.write(req); proc.stdin.flush()
        resp = json.loads(proc.stdout.readline())
        assert resp["error"]["code"] == -32601
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)
