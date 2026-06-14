"""Tests for organizer.* broker commands."""

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


def test_organizer_refresh_main_thread_success(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=60: fn()

    result = bridge._handle_organizer_refresh(organizer, pump, {"save_changes": True})

    assert result["ok"] is True
    assert result["result"]["refreshed"] is True
    assert result["result"]["save_changes"] is True
    assert "timestamp_ms" in result["result"]
    organizer.refresh.assert_called_once_with(True)


def test_organizer_refresh_default_save_changes_true(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=60: fn()

    result = bridge._handle_organizer_refresh(organizer, pump, {})

    assert result["ok"] is True
    organizer.refresh.assert_called_once_with(True)


def test_organizer_refresh_timeout_returns_error(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()
    pump.invoke_blocking.side_effect = TimeoutError("pump timeout")

    result = bridge._handle_organizer_refresh(organizer, pump, {})

    assert result["ok"] is False
    assert result["error"]["code"] == "main_thread_unavailable"
