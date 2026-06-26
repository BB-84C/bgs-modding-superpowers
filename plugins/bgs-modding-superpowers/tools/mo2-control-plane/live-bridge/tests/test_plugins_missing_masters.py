"""Tests for plugins.missing_masters broker command."""

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
        types.SimpleNamespace(
            IPluginTool=object,
            VersionInfo=lambda *args: args,
            PluginState=types.SimpleNamespace(MISSING=0, INACTIVE=1, ACTIVE=2),
        ),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: _FakeWinDll(), raising=False)

    sys.modules.pop("mo2_agent_control", None)
    return importlib.import_module("mo2_agent_control")


def _pump():
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()
    return pump


def _organizer(plugin_names, state_map, masters_map):
    plugin_list = MagicMock()
    plugin_list.pluginNames.return_value = plugin_names
    plugin_list.state.side_effect = lambda name: state_map.get(name, 0)
    plugin_list.masters.side_effect = lambda name: masters_map.get(name, [])
    organizer = MagicMock()
    organizer.pluginList.return_value = plugin_list
    return organizer


def test_missing_masters_default_scan_reports_enabled_plugins_only(monkeypatch):
    bridge = _load_bridge(monkeypatch)
    organizer = _organizer(
        ["A.esm", "B.esm", "C.esm"],
        {"A.esm": 2, "B.esm": 2, "C.esm": 1},
        {"A.esm": ["B.esm", "missing.esm"], "B.esm": [], "C.esm": ["A.esm"]},
    )

    result = bridge._handle_plugins_missing_masters(organizer, _pump(), {})

    assert result["ok"] is True
    assert result["warnings"] == [
        {
            "plugin": "A.esm",
            "missing_masters": ["missing.esm"],
            "enabled_masters": ["B.esm"],
            "declared_masters": ["B.esm", "missing.esm"],
        }
    ]
    assert result["scanned_count"] == 2
    assert result["enabled_count"] == 2


def test_missing_masters_compares_case_insensitively(monkeypatch):
    bridge = _load_bridge(monkeypatch)
    organizer = _organizer(
        ["A.esm", "B.ESM"],
        {"A.esm": 2, "B.ESM": 2},
        {"A.esm": ["b.esm"], "B.ESM": []},
    )

    result = bridge._handle_plugins_missing_masters(organizer, _pump(), {})

    assert result["warnings"] == []
    assert result["scanned_count"] == 2


def test_missing_masters_names_filter_skips_unknown(monkeypatch):
    bridge = _load_bridge(monkeypatch)
    organizer = _organizer(["A.esm"], {"A.esm": 2}, {"A.esm": ["missing.esm"]})

    result = bridge._handle_plugins_missing_masters(organizer, _pump(), {"names": ["UNKNOWN.esm"]})

    assert result["warnings"] == []
    assert result["scanned_count"] == 0
    assert result["enabled_count"] == 1


def test_missing_masters_names_filter_matches_case_insensitively(monkeypatch):
    bridge = _load_bridge(monkeypatch)
    organizer = _organizer(["A.esm", "B.esm"], {"A.esm": 2, "B.esm": 2}, {"A.esm": ["missing.esm"]})

    result = bridge._handle_plugins_missing_masters(organizer, _pump(), {"names": ["a.esm"]})

    assert result["warnings"][0]["plugin"] == "A.esm"
    assert result["warnings"][0]["missing_masters"] == ["missing.esm"]
    assert result["scanned_count"] == 1
    assert result["enabled_count"] == 2
