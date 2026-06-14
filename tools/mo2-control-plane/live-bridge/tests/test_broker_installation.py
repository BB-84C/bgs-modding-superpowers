"""Tests for installation.* broker commands."""

import ctypes
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


LIVE_BRIDGE_DIR = Path(__file__).resolve().parents[1]


class _FakeWinFunction:
    def __call__(self, *args, **kwargs):
        return 1


class _FakeWinDll:
    def __getattr__(self, name):
        function = _FakeWinFunction()
        setattr(self, name, function)
        return function


def _load_bridge(monkeypatch):
    monkeypatch.syspath_prepend(str(LIVE_BRIDGE_DIR))
    monkeypatch.setitem(
        sys.modules,
        "mobase",
        types.SimpleNamespace(IPluginTool=object, VersionInfo=lambda *args: args),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: _FakeWinDll(), raising=False)

    sys.modules.pop("mo2_agent_control", None)
    return importlib.import_module("mo2_agent_control")


def test_installation_install_local_archive_success(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    archive = tmp_path / "TestMod.7z"
    archive.write_bytes(b"fake archive")

    new_mod = MagicMock()
    new_mod.name.return_value = "TestMod"
    new_mod.absolutePath.return_value = "/path/to/mods/TestMod"
    organizer = MagicMock()
    organizer.installMod.return_value = new_mod
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=120: fn()

    result = bridge._handle_installation_install_local_archive(
        organizer,
        pump,
        {
            "archive_path": str(archive),
            "name_suggestion": "TestMod",
        },
    )

    assert result["ok"] is True
    r = result["result"]
    assert r["name"] == "TestMod"
    assert r["installation_file"] == str(archive)


def test_installation_install_local_archive_canceled(monkeypatch, tmp_path):
    """installMod returns None on cancellation or failure."""
    bridge = _load_bridge(monkeypatch)

    archive = tmp_path / "CanceledMod.7z"
    archive.write_bytes(b"fake archive")

    organizer = MagicMock()
    organizer.installMod.return_value = None
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=120: fn()

    result = bridge._handle_installation_install_local_archive(
        organizer,
        pump,
        {
            "archive_path": str(archive),
            "name_suggestion": "",
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "internal_error"
    assert "None" in result["error"]["message"] or "canceled" in result["error"]["message"].lower()


def test_installation_install_local_archive_missing_file(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()

    result = bridge._handle_installation_install_local_archive(
        organizer,
        pump,
        {
            "archive_path": "/nonexistent/path.7z",
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"
    assert "not found" in result["error"]["message"].lower()
