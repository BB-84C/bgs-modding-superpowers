"""Tests for profile.* broker commands."""

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


def test_profile_list_enumerates_dirs_with_modlist(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    base = tmp_path / "mo2"
    profiles_root = base / "profiles"
    profiles_root.mkdir(parents=True)

    (profiles_root / "Default").mkdir()
    (profiles_root / "Default" / "modlist.txt").write_text("", encoding="utf-8")
    (profiles_root / "Default" / "settings.txt").write_text("", encoding="utf-8")

    (profiles_root / "Test").mkdir()
    (profiles_root / "Test" / "modlist.txt").write_text("", encoding="utf-8")

    (profiles_root / "Junk").mkdir()
    (profiles_root / "Junk" / "random.txt").write_text("", encoding="utf-8")

    organizer = MagicMock()
    organizer.basePath.return_value = str(base)

    result = bridge._handle_profile_list(organizer, {})

    assert result["ok"] is True
    names = [profile["name"] for profile in result["result"]["profiles"]]
    assert sorted(names) == ["Default", "Test"]
    default_entry = next(profile for profile in result["result"]["profiles"] if profile["name"] == "Default")
    assert default_entry["has_local_inis"] is True
    test_entry = next(profile for profile in result["result"]["profiles"] if profile["name"] == "Test")
    assert test_entry["has_local_inis"] is False


def test_profile_list_handles_missing_profiles_root(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    base = tmp_path / "mo2"
    base.mkdir()
    organizer = MagicMock()
    organizer.basePath.return_value = str(base)

    result = bridge._handle_profile_list(organizer, {})

    assert result["ok"] is True
    assert result["result"]["profiles"] == []


def test_profile_active_returns_name_and_path(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    organizer.profileName.return_value = "Default"
    organizer.profilePath.return_value = "/path/to/profiles/Default"

    result = bridge._handle_profile_active(organizer, {})

    assert result["ok"] is True
    assert result["result"]["name"] == "Default"
    assert result["result"]["path"] == "/path/to/profiles/Default"
