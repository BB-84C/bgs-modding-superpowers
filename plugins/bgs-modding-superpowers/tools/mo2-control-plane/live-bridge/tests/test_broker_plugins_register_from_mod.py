"""Tests for plugins.register_from_mod broker command."""

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


class _FakeMod:
    def __init__(self, root: Path):
        self._root = root

    def absolutePath(self):
        return str(self._root)


class _FakeModList:
    def __init__(self, mod_name: str, mod_root: Path | None):
        self.mod_name = mod_name
        self.mod_root = mod_root

    def getMod(self, name: str):
        if self.mod_root is not None and name == self.mod_name:
            return _FakeMod(self.mod_root)
        return None


class _FakePluginList:
    def __init__(self, names: list[str]):
        self.names = list(names)
        self.callbacks = []
        self.callback_calls = {}

    def pluginNames(self):
        return list(self.names)

    def priority(self, name):
        return self.names.index(name)

    def state(self, _name):
        return 2

    def hasMasterExtension(self, name):
        return name.lower().endswith(".esm")

    def onRefreshed(self, callback):
        self.callbacks.append(callback)
        self.callback_calls.setdefault(id(callback), 0)
        return True


class _FakeOrganizer:
    def __init__(
        self,
        profile_dir: Path,
        mod_list,
        plugin_list,
        *,
        settle_refresh=True,
        fire_refresh=True,
        settle_after_refresh_calls=1,
    ):
        self.profile_dir = profile_dir
        self._mod_list = mod_list
        self._plugin_list = plugin_list
        self.settle_refresh = settle_refresh
        self.fire_refresh = fire_refresh
        self.settle_after_refresh_calls = settle_after_refresh_calls
        self.refresh_calls = []

    def modList(self):
        return self._mod_list

    def pluginList(self):
        return self._plugin_list

    def profilePath(self):
        return str(self.profile_dir)

    def refresh(self, save_changes=False):
        self.refresh_calls.append(save_changes)
        if self.settle_refresh and len(self.refresh_calls) >= self.settle_after_refresh_calls:
            plugins_txt = self.profile_dir / "plugins.txt"
            if plugins_txt.exists():
                for line in plugins_txt.read_text(encoding="utf-8").splitlines():
                    name = line.lstrip("*").strip()
                    if name and not line.startswith("#") and name not in self._plugin_list.names:
                        self._plugin_list.names.append(name)
        if self.fire_refresh:
            for callback in list(self._plugin_list.callbacks):
                self._plugin_list.callback_calls[id(callback)] = self._plugin_list.callback_calls.get(id(callback), 0) + 1
                callback()


def _pump():
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()
    return pump


def test_plugins_register_from_mod_writes_plugins_txt_and_waits_for_on_refreshed(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "plugins.txt").write_text("# comment\n*Existing.esm\n", encoding="utf-8")
    mod_root = tmp_path / "mods" / "FreshMod"
    (mod_root / "Data").mkdir(parents=True)
    (mod_root / "FreshA.esp").write_text("fake", encoding="utf-8")
    (mod_root / "Data" / "FreshB.esm").write_text("fake", encoding="utf-8")

    plugin_list = _FakePluginList(["Existing.esm"])
    organizer = _FakeOrganizer(profile_dir, _FakeModList("FreshMod", mod_root), plugin_list)

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "FreshMod"})

    assert result["ok"] is True
    assert result["result"]["plugins_added"] == ["FreshA.esp", "FreshB.esm"]
    assert result["result"]["refresh_settled"] is True
    assert [entry["name"] for entry in result["result"]["plugins_registered"]] == ["FreshA.esp", "FreshB.esm"]
    plugins_txt = (profile_dir / "plugins.txt").read_text(encoding="utf-8")
    assert "*FreshA.esp" in plugins_txt
    assert "*FreshB.esm" in plugins_txt
    assert organizer.refresh_calls == [False]
    assert result["result"]["refresh_attempts"] == 1


def test_plugins_register_from_mod_mod_not_found(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    organizer = _FakeOrganizer(profile_dir, _FakeModList("FreshMod", None), _FakePluginList([]))

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "FreshMod"})

    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"


def test_plugins_register_from_mod_no_new_plugins_skips_write_and_refresh(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    mod_root = tmp_path / "mods" / "AlreadyThere"
    mod_root.mkdir(parents=True)
    (mod_root / "Already.esp").write_text("fake", encoding="utf-8")
    plugin_list = _FakePluginList(["Already.esp"])
    organizer = _FakeOrganizer(profile_dir, _FakeModList("AlreadyThere", mod_root), plugin_list)

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "AlreadyThere"})

    assert result["ok"] is True
    assert result["result"]["plugins_added"] == []
    assert result["result"]["refresh_settled"] is True
    assert not (profile_dir / "plugins.txt").exists()
    assert organizer.refresh_calls == []


def test_plugins_register_from_mod_refresh_timeout(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    mod_root = tmp_path / "mods" / "TimeoutMod"
    mod_root.mkdir(parents=True)
    (mod_root / "Timeout.esp").write_text("fake", encoding="utf-8")
    organizer = _FakeOrganizer(
        profile_dir,
        _FakeModList("TimeoutMod", mod_root),
        _FakePluginList([]),
        fire_refresh=False,
    )

    monkeypatch.setattr(bridge.threading.Event, "wait", lambda self, timeout=None: False)
    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "TimeoutMod"})

    assert result["ok"] is False
    assert result["error"]["code"] == "refresh_timeout"


def test_plugins_register_from_mod_refresh_callback_can_report_unsettled(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    mod_root = tmp_path / "mods" / "UnsettledMod"
    mod_root.mkdir(parents=True)
    (mod_root / "Unsettled.esp").write_text("fake", encoding="utf-8")
    organizer = _FakeOrganizer(
        profile_dir,
        _FakeModList("UnsettledMod", mod_root),
        _FakePluginList([]),
        settle_refresh=False,
    )

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "UnsettledMod"})

    assert result["ok"] is True
    assert result["result"]["plugins_added"] == ["Unsettled.esp"]
    assert result["result"]["plugins_registered"] == []
    assert result["result"]["refresh_settled"] is False
    assert result["result"]["refresh_attempts"] == 2
    assert organizer.refresh_calls == [False, False]


def test_plugins_register_from_mod_retries_once_when_first_refresh_does_not_settle(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    mod_root = tmp_path / "mods" / "RetryMod"
    mod_root.mkdir(parents=True)
    (mod_root / "Retry.esp").write_text("fake", encoding="utf-8")
    organizer = _FakeOrganizer(
        profile_dir,
        _FakeModList("RetryMod", mod_root),
        _FakePluginList([]),
        settle_after_refresh_calls=2,
    )

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "RetryMod"})

    assert result["ok"] is True
    assert result["result"]["plugins_added"] == ["Retry.esp"]
    assert [entry["name"] for entry in result["result"]["plugins_registered"]] == ["Retry.esp"]
    assert result["result"]["refresh_settled"] is True
    assert result["result"]["refresh_attempts"] == 2
    assert organizer.refresh_calls == [False, False]


def test_plugins_register_from_mod_preserves_crlf_plugins_txt(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "plugins.txt").write_text("# comment\r\n*Existing.esm\r\n", encoding="utf-8", newline="")
    mod_root = tmp_path / "mods" / "CrlfMod"
    mod_root.mkdir(parents=True)
    (mod_root / "Crlf.esp").write_text("fake", encoding="utf-8")
    organizer = _FakeOrganizer(profile_dir, _FakeModList("CrlfMod", mod_root), _FakePluginList(["Existing.esm"]))

    result = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "CrlfMod"})

    assert result["ok"] is True
    raw = (profile_dir / "plugins.txt").read_bytes()
    assert b"*Existing.esm\r\n*Crlf.esp\r\n" in raw


def test_plugins_register_from_mod_persistent_prior_callbacks_are_one_shot_guarded(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    plugin_list = _FakePluginList([])

    mod_one_root = tmp_path / "mods" / "OneMod"
    mod_one_root.mkdir(parents=True)
    (mod_one_root / "One.esp").write_text("fake", encoding="utf-8")
    organizer = _FakeOrganizer(profile_dir, _FakeModList("OneMod", mod_one_root), plugin_list)
    first = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "OneMod"})
    first_callback = plugin_list.callbacks[0]

    mod_two_root = tmp_path / "mods" / "TwoMod"
    mod_two_root.mkdir(parents=True)
    (mod_two_root / "Two.esp").write_text("fake", encoding="utf-8")
    organizer._mod_list = _FakeModList("TwoMod", mod_two_root)
    second = bridge._handle_plugins_register_from_mod(organizer, _pump(), {"mod_name": "TwoMod"})

    assert first["ok"] is True
    assert first["result"]["plugins_added"] == ["One.esp"]
    assert second["ok"] is True
    assert second["result"]["plugins_added"] == ["Two.esp"]
    assert plugin_list.callback_calls[id(first_callback)] >= 2


def test_plugins_register_from_mod_rejects_empty_mod_name(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    result = bridge._handle_plugins_register_from_mod(MagicMock(), MagicMock(), {"mod_name": "   "})

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"
