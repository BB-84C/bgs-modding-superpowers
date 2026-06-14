"""Tests for mods.* broker commands."""

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


def test_mods_list_returns_mods_with_priority_enabled_and_separator(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    mod_list = MagicMock()
    organizer.modList.return_value = mod_list

    mod_list.allMods.return_value = ["ModA", "ModB", "Section_separator"]
    mod_list.priority.side_effect = lambda n: {"ModA": 0, "ModB": 1, "Section_separator": 2}[n]
    # P-F4: ModState.ACTIVE is the truth. Stub state values that imitate the flag mask.
    mod_list.state.side_effect = lambda n: {"ModA": 2, "ModB": 0, "Section_separator": 0}[n]

    # Configure getMod for P-F5 separator detection — return mod stubs whose isSeparator() is true only for the *_separator one
    def _get_mod(name):
        m = MagicMock()
        m.isSeparator.return_value = name.endswith("_separator")
        return m

    mod_list.getMod.side_effect = _get_mod

    result = bridge._handle_mods_list(organizer=organizer, payload={})

    assert result["ok"] is True
    mods = result["result"]["mods"]
    assert len(mods) == 3
    names = [m["name"] for m in mods]
    assert names == ["ModA", "ModB", "Section_separator"]
    assert mods[0]["enabled"] is True
    assert mods[1]["enabled"] is False
    assert mods[2]["is_separator"] is True
    assert mods[0]["is_separator"] is False
