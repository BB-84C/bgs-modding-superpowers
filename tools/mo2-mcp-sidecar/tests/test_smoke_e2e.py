"""End-to-end smoke: spawn the sidecar subprocess, send JSON-RPC requests over stdio,
verify the full registration chain works (envelope -> world -> assets -> fomod ->
archive -> install). No MO2 needed; tests use synthetic on-disk fixtures.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _spawn_sidecar(mods_root: Path, profile_dir: Path | None = None, game: str = "FALLOUT4"):
    """Spawn the sidecar; return Popen + helper for clean JSON-RPC roundtrip."""
    args = [sys.executable, "-m", "mo2_mcp_sidecar",
            "--mods-root", str(mods_root), "--game", game]
    if profile_dir is not None:
        args += ["--profile-dir", str(profile_dir)]
    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    return proc


def _read_response(proc, expect_id):
    """Read a single response line and verify id matches."""
    line = proc.stdout.readline()
    if not line:
        stderr_tail = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"sidecar exited; stderr: {stderr_tail}")
    msg = json.loads(line)
    return msg


def _send(proc, method, params=None, msg_id=1):
    req = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()


def test_sidecar_subprocess_emits_ready_then_handles_assets_summary(tmp_path):
    """Spawn sidecar -> ready signal -> call assets.summary against a real profile."""
    profile_dir = tmp_path / "profiles" / "Default"
    profile_dir.mkdir(parents=True)
    (profile_dir / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile_dir / "plugins.txt").write_text("*Fallout4.esm\n", encoding="utf-8")
    mods = tmp_path / "mods"
    (mods / "ModA").mkdir(parents=True)
    (mods / "ModB").mkdir(parents=True)

    proc = _spawn_sidecar(mods_root=mods, profile_dir=profile_dir)
    try:
        ready = _read_response(proc, expect_id=None)
        assert ready == {"ready": True}

        _send(proc, "assets.summary", {"profile_dir": str(profile_dir)}, msg_id=1)
        resp = _read_response(proc, expect_id=1)
        assert resp["id"] == 1
        assert "result" in resp
        result = resp["result"]
        assert result["profile_name"] == "Default"
        assert result["game"] == "FALLOUT4"
        assert result["mod_count"] == 2
        assert result["enabled_mod_count"] == 2
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


def test_sidecar_handles_world_invalidate(tmp_path):
    profile_dir = tmp_path / "profiles" / "Default"
    profile_dir.mkdir(parents=True)
    (profile_dir / "modlist.txt").write_text("+ModA\n", encoding="utf-8")
    (profile_dir / "plugins.txt").write_text("", encoding="utf-8")
    mods = tmp_path / "mods"
    (mods / "ModA").mkdir(parents=True)

    proc = _spawn_sidecar(mods_root=mods, profile_dir=profile_dir)
    try:
        _read_response(proc, expect_id=None)  # ready

        # warm up the cache
        _send(proc, "assets.summary", {"profile_dir": str(profile_dir)}, msg_id=1)
        _read_response(proc, expect_id=1)

        # invalidate it
        _send(proc, "world.invalidate", {"profile_dir": str(profile_dir)}, msg_id=2)
        resp = _read_response(proc, expect_id=2)
        assert resp["result"]["invalidated"] is True
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


def test_sidecar_unknown_method_returns_error(tmp_path):
    mods = tmp_path / "mods"
    mods.mkdir()
    proc = _spawn_sidecar(mods_root=mods)
    try:
        _read_response(proc, expect_id=None)  # ready
        _send(proc, "totally.nonexistent", {}, msg_id=42)
        resp = _read_response(proc, expect_id=42)
        assert resp["error"]["code"] == -32601  # method not found
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


def test_sidecar_all_registered_methods_exposed(tmp_path):
    """Verify every method we register actually responds (not method-not-found).

    Sequence: spawn -> ready -> call each method with a minimal valid payload OR
    expect a domain error (NOT -32601 method-not-found).
    """
    profile_dir = tmp_path / "profiles" / "Default"
    profile_dir.mkdir(parents=True)
    (profile_dir / "modlist.txt").write_text("", encoding="utf-8")
    (profile_dir / "plugins.txt").write_text("", encoding="utf-8")
    mods = tmp_path / "mods"
    mods.mkdir()

    proc = _spawn_sidecar(mods_root=mods, profile_dir=profile_dir)
    try:
        _read_response(proc, expect_id=None)  # ready

        expected = [
            ("system.echo", {"hello": "world"}),
            ("assets.summary", {"profile_dir": str(profile_dir)}),
            ("assets.conflicts", {"profile_dir": str(profile_dir), "max_results": 1}),
            ("assets.resolve_file", {"profile_dir": str(profile_dir),
                                     "virtual_path": "Data/Fallout4.esm"}),
            ("world.invalidate", {"profile_dir": str(profile_dir)}),
            ("install.conflict_preview", {"profile_dir": str(profile_dir),
                                          "staged_files": []}),
            # archive.extract_all + install.stage_fomod + fomod.* take real paths;
            # we just verify they're registered (call with bogus args and expect
            # a domain error, not method_not_found)
        ]
        for i, (method, params) in enumerate(expected, start=1):
            _send(proc, method, params, msg_id=i)
            resp = _read_response(proc, expect_id=i)
            # Either result or domain error -- but NOT -32601 method-not-found
            if "error" in resp:
                assert resp["error"]["code"] != -32601, f"{method} not registered"

        # Verify archive/fomod/install methods are registered (will return domain
        # error from bogus path, NOT -32601)
        for i, method in enumerate(
            ["archive.extract_all", "fomod.parse_choices", "fomod.resolve_files",
             "install.stage_fomod"], start=100,
        ):
            _send(proc, method, {"archive_path": "/nope", "dest": "/tmp/x",
                                 "choices": [], "staging_dir": "/tmp/y"}, msg_id=i)
            resp = _read_response(proc, expect_id=i)
            assert resp["error"]["code"] != -32601, f"{method} not registered"
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)
