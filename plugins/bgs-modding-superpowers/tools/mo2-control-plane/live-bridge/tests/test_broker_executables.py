"""Tests for executables.list broker handler."""

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


def test_executables_list_via_handler(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    base = tmp_path / "mo2"
    base.mkdir()
    (base / "ModOrganizer.ini").write_text(
        r"""
[customExecutables]
size=1
1\title=xEdit
1\binary=C:/Tools/xEdit.exe
1\arguments=-fo4
1\workingDirectory=
1\steamAppID=
1\ownicon=true
1\hide=false
""",
        encoding="utf-8",
    )

    organizer = MagicMock()
    organizer.basePath.return_value = str(base)

    result = bridge._handle_executables_list(organizer, {})

    assert result["ok"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["executables"][0]["title"] == "xEdit"


def test_executables_list_no_ini_returns_error(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    base = tmp_path / "mo2"
    base.mkdir()

    organizer = MagicMock()
    organizer.basePath.return_value = str(base)

    result = bridge._handle_executables_list(organizer, {})

    assert result["ok"] is False
    assert result["error"]["code"] == "internal_error"
    assert "ModOrganizer.ini" in result["error"]["message"]
