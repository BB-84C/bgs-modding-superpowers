"""Tests for plugins.* broker commands."""

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


def test_plugins_list_returns_all_plugins_with_state_priority_load_order(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    plugin_list = MagicMock()
    plugin_list.pluginNames.return_value = ["Fallout4.esm", "ModA.esp", "ModB.esp"]
    plugin_list.state.side_effect = lambda name: 2 if name in ("Fallout4.esm", "ModA.esp") else 0
    plugin_list.priority.side_effect = lambda name: {"Fallout4.esm": 0, "ModA.esp": 1, "ModB.esp": 2}[
        name
    ]
    plugin_list.loadOrder.side_effect = lambda name: 0 if name == "Fallout4.esm" else (1 if name == "ModA.esp" else -1)
    plugin_list.origin.side_effect = lambda name: {
        "Fallout4.esm": "data",
        "ModA.esp": "ModA",
        "ModB.esp": "ModB",
    }[name]
    plugin_list.isMasterFlagged.side_effect = lambda name: name.endswith(".esm")
    plugin_list.isLightFlagged.side_effect = lambda name: False
    plugin_list.hasMasterExtension.side_effect = lambda name: name.endswith(".esm")
    plugin_list.hasLightExtension.side_effect = lambda name: name.endswith(".esl")

    organizer = MagicMock()
    organizer.pluginList.return_value = plugin_list

    result = bridge._handle_plugins_list(organizer, {})

    assert result["ok"] is True
    plugins = result["result"]["plugins"]
    assert len(plugins) == 3
    fallout4 = plugins[0]
    assert fallout4["name"] == "Fallout4.esm"
    assert fallout4["enabled"] is True
    assert fallout4["priority"] == 0
    assert fallout4["load_order"] == 0
    assert fallout4["origin"] == "data"
    assert fallout4["is_master"] is True
    assert fallout4["is_light"] is False

    mod_b = plugins[2]
    assert mod_b["enabled"] is False
    assert mod_b["load_order"] == -1


def test_plugins_list_empty(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    plugin_list = MagicMock()
    plugin_list.pluginNames.return_value = []
    organizer = MagicMock()
    organizer.pluginList.return_value = plugin_list

    result = bridge._handle_plugins_list(organizer, {})

    assert result["ok"] is True
    assert result["result"]["plugins"] == []


def test_plugins_list_handles_origin_overwrite(monkeypatch):
    """Plugin origin can be 'overwrite' (special marker)."""

    bridge = _load_bridge(monkeypatch)

    plugin_list = MagicMock()
    plugin_list.pluginNames.return_value = ["TestOverwrite.esp"]
    plugin_list.state.return_value = 2
    plugin_list.priority.return_value = 0
    plugin_list.loadOrder.return_value = 0
    plugin_list.origin.return_value = "overwrite"
    plugin_list.isMasterFlagged.return_value = False
    plugin_list.isLightFlagged.return_value = False
    plugin_list.hasMasterExtension.return_value = False
    plugin_list.hasLightExtension.return_value = False

    organizer = MagicMock()
    organizer.pluginList.return_value = plugin_list

    result = bridge._handle_plugins_list(organizer, {})

    assert result["result"]["plugins"][0]["origin"] == "overwrite"
