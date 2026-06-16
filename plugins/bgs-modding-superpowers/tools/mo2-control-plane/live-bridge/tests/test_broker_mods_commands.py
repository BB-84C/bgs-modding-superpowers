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


def test_mods_set_active_single_with_readback(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    state = {"ModA": False}
    mod_list = MagicMock()

    def _set_active(name, active):
        if isinstance(name, list):
            for n in name:
                state[n] = active
            return len(name)
        state[name] = active
        return True

    mod_list.setActive.side_effect = _set_active
    mod_list.state.side_effect = lambda n: 2 if state.get(n) else 0

    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_active(organizer, pump, {"names": ["ModA"], "active": True})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["requested"] == ["ModA"]
    assert readback["applied"] == ["ModA"]
    assert readback["failed"] == []
    assert readback["readback"] == [{"name": "ModA", "active": True}]


def test_mods_set_active_partial_failure(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.setActive.return_value = 1
    states = {"ModA": True, "ModB": False}
    mod_list.state.side_effect = lambda n: 2 if states[n] else 0

    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_active(
        organizer,
        pump,
        {"names": ["ModA", "ModB"], "active": True},
    )

    assert result["ok"] is True
    readback = result["result"]
    assert readback["applied"] == ["ModA"]
    assert readback["failed"] == ["ModB"]
    assert readback["readback"][0]["name"] == "ModA"
    assert readback["readback"][0]["active"] is True
    assert readback["readback"][1]["name"] == "ModB"
    assert readback["readback"][1]["active"] is False


def test_mods_set_active_invalid_params_returns_error(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    result = bridge._handle_mods_set_active(
        MagicMock(),
        MagicMock(),
        {"names": "ModA", "active": True},
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"

    response = bridge.dispatch_transport_request(
        {
            "protocol_version": "1",
            "request_id": "req-001",
            "method": "mods.set_active",
            "payload": {"names": "ModA", "active": True},
        },
        bridge.build_command_handlers(organizer=MagicMock(), main_thread_pump=MagicMock()),
    )

    assert response["ok"] is False
    assert response["result"] is None
    assert response["error"]["code"] == "invalid_params"


def test_mods_set_priority_success(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    actual = {"current": 0}
    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    mod_list.allMods.return_value = ["ModA", "ModB", "ModC"]

    def _set(_name, priority):
        actual["current"] = priority

    mod_list.setPriority.side_effect = _set
    mod_list.priority.side_effect = lambda _name: actual["current"]

    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_priority(organizer, pump, {"name": "ModA", "priority": 1})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["name"] == "ModA"
    assert readback["requested_priority"] == 1
    assert readback["actual_priority"] == 1
    assert readback["noop"] is False


def test_mods_set_priority_silent_noop_detected(monkeypatch):
    """oracle §2.1: setPriority returns true even when no-op on master/non-master inversion."""
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    mod_list.allMods.return_value = ["ModA", "ModB", "ModC"]
    mod_list.setPriority = MagicMock()
    mod_list.priority.return_value = 0

    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_priority(organizer, pump, {"name": "ModA", "priority": 2})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["actual_priority"] == 0
    assert readback["noop"] is True


def test_mods_set_priority_mod_not_found(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_priority(organizer, pump, {"name": "NoSuch", "priority": 0})

    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"


def test_mods_set_priority_out_of_range(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    mod_list.allMods.return_value = ["ModA", "ModB"]
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=10: fn()

    result = bridge._handle_mods_set_priority(organizer, pump, {"name": "ModA", "priority": -1})

    assert result["ok"] is False
    assert result["error"]["code"] == "priority_out_of_range"


def test_mods_rename_success(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    old_mod = MagicMock()
    mod_list.getMod.side_effect = lambda name: old_mod if name == "OldName" else None
    refreshed = MagicMock()
    refreshed.name.return_value = "NewName"
    mod_list.renameMod.return_value = refreshed
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()

    result = bridge._handle_mods_rename(organizer, pump, {"old_name": "OldName", "new_name": "NewName"})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["old_name"] == "OldName"
    assert readback["new_name"] == "NewName"
    assert readback["name_was_sanitized"] is False


def test_mods_rename_sanitizes_illegal_chars(monkeypatch):
    """Bad path chars get stripped before calling MO2 (avoids Qt dialog)."""
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    old_mod = MagicMock()

    def _get(name):
        if name == "OldName":
            return old_mod
        if name == "BadName":
            return None
        return None

    mod_list.getMod.side_effect = _get
    refreshed = MagicMock()
    refreshed.name.return_value = "BadName"
    mod_list.renameMod.return_value = refreshed
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()

    result = bridge._handle_mods_rename(organizer, pump, {"old_name": "OldName", "new_name": "Bad<>Name"})

    assert result["ok"] is True
    assert result["result"]["new_name"] == "BadName"
    assert result["result"]["name_was_sanitized"] is True
    mod_list.renameMod.assert_called_once_with(old_mod, "BadName")


def test_mods_rename_not_found_returns_error(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()

    result = bridge._handle_mods_rename(organizer, pump, {"old_name": "NoSuch", "new_name": "Whatever"})

    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"


def test_mods_rename_collision_returns_error(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()

    result = bridge._handle_mods_rename(organizer, pump, {"old_name": "OldName", "new_name": "AlsoExists"})

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"
    assert "exists" in result["error"]["message"].lower()


def test_mods_rename_empty_after_sanitize_returns_error(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()

    result = bridge._handle_mods_rename(organizer, pump, {"old_name": "OldName", "new_name": "<>:?*"})

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"


def test_mods_remove_success(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod = MagicMock()
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    mod_list.removeMod.return_value = True
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=30: fn()

    result = bridge._handle_mods_remove(organizer, pump, {"name": "ModA"})

    assert result["ok"] is True
    assert result["result"]["name"] == "ModA"
    assert result["result"]["removed"] is True
    mod_list.removeMod.assert_called_once_with(mod)


def test_mods_remove_not_found(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=30: fn()

    result = bridge._handle_mods_remove(organizer, pump, {"name": "NoSuch"})

    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"
    mod_list.removeMod.assert_not_called()


def test_mods_remove_failure_from_modlist(monkeypatch):
    """MO2 returned False from removeMod (e.g., locked file)."""
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    mod_list.removeMod.return_value = False
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=30: fn()

    result = bridge._handle_mods_remove(organizer, pump, {"name": "ModA"})

    assert result["ok"] is False
    assert result["error"]["code"] == "internal_error"


def test_mods_create_basic(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    new_mod = MagicMock()
    new_mod.name.return_value = "NewMod"
    mod_path = tmp_path / "NewMod"
    new_mod.absolutePath.return_value = str(mod_path)
    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    mod_list.priority.return_value = 5
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    organizer.createMod.return_value = new_mod

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()
    monkeypatch.setattr(bridge, "GuessedString", lambda name: name, raising=False)

    result = bridge._handle_mods_create(organizer, pump, {"name": "NewMod"})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["name"] == "NewMod"
    assert readback["created"] is True
    assert readback["priority"] == 5
    assert readback["absolute_path"] == str(mod_path)
    assert mod_path.is_dir()


def test_mods_create_with_target_priority(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    new_mod = MagicMock()
    new_mod.name.return_value = "NewMod"
    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    state = {"current": 0}

    def _set(_name, priority):
        state["current"] = priority

    mod_list.setPriority.side_effect = _set
    mod_list.priority.side_effect = lambda _name: state["current"]

    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    organizer.createMod.return_value = new_mod

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()
    monkeypatch.setattr(bridge, "GuessedString", lambda name: name, raising=False)

    result = bridge._handle_mods_create(organizer, pump, {"name": "NewMod", "priority": 3})

    assert result["ok"] is True
    assert result["result"]["priority"] == 3
    assert result["result"]["requested_priority"] == 3
    organizer.modDataChanged.assert_called_once_with(new_mod)


def test_mods_create_name_collision(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = MagicMock()
    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()
    monkeypatch.setattr(bridge, "GuessedString", lambda name: name, raising=False)

    result = bridge._handle_mods_create(organizer, pump, {"name": "ExistingMod"})

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"
    assert "exists" in result["error"]["message"].lower()


def test_mods_create_sanitizes_name(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    captured = {}
    new_mod = MagicMock()
    new_mod.name.return_value = "BadName"
    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    mod_list.priority.return_value = 0
    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    def _create(guessed_string):
        captured["name"] = guessed_string
        return new_mod

    organizer.createMod.side_effect = _create

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()
    monkeypatch.setattr(bridge, "GuessedString", lambda name: name, raising=False)

    result = bridge._handle_mods_create(organizer, pump, {"name": "Bad<>Name"})

    assert result["ok"] is True
    assert captured["name"] == "BadName"


def test_mods_create_returns_internal_error_on_none(monkeypatch):
    """createMod returned None (e.g., MO2 internal failure)."""
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    organizer.createMod.return_value = None

    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=15: fn()
    monkeypatch.setattr(bridge, "GuessedString", lambda name: name, raising=False)

    result = bridge._handle_mods_create(organizer, pump, {"name": "Whatever"})

    assert result["ok"] is False
    assert result["error"]["code"] == "internal_error"


def test_mods_meta_read_existing(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    mod_dir = tmp_path / "ModA"
    mod_dir.mkdir()
    meta = mod_dir / "meta.ini"
    meta.write_text(
        '[General]\nversion=1.2.3\nnotes="hello"\n[Nexus]\nnexusID=12345\n',
        encoding="utf-8",
    )

    mod = MagicMock()
    mod.absolutePath.return_value = str(mod_dir)
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    result = bridge._handle_mods_meta_read(organizer, {"name": "ModA"})

    assert result["ok"] is True
    readback = result["result"]
    assert readback["name"] == "ModA"
    assert readback["exists"] is True
    assert readback["meta"]["General"]["version"] == "1.2.3"
    assert readback["meta"]["Nexus"]["nexusID"] == "12345"


def test_mods_meta_read_no_meta_ini(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)

    mod_dir = tmp_path / "ModB"
    mod_dir.mkdir()

    mod = MagicMock()
    mod.absolutePath.return_value = str(mod_dir)
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    result = bridge._handle_mods_meta_read(organizer, {"name": "ModB"})

    assert result["ok"] is True
    assert result["result"]["exists"] is False
    assert result["result"]["meta"] == {}


def test_mods_meta_read_not_found(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list

    result = bridge._handle_mods_meta_read(organizer, {"name": "NoSuch"})

    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"


def test_mods_meta_write_creates_meta_ini(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    import configparser

    mod_dir = tmp_path / "ModA"
    mod_dir.mkdir()
    mod = MagicMock()
    mod.absolutePath.return_value = str(mod_dir)
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=5: fn()

    result = bridge._handle_mods_meta_write(
        organizer,
        pump,
        {"name": "ModA", "updates": {"General": {"version": "1.0.0", "notes": '"hello"'}}},
    )

    assert result["ok"] is True
    assert result["result"]["name"] == "ModA"
    assert "General" in result["result"]["updated_sections"]
    organizer.modDataChanged.assert_called_once_with(mod)

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(mod_dir / "meta.ini", encoding="utf-8")
    assert parser["General"]["version"] == "1.0.0"


def test_mods_meta_write_merges_existing(monkeypatch, tmp_path):
    bridge = _load_bridge(monkeypatch)
    import configparser

    mod_dir = tmp_path / "ModA"
    mod_dir.mkdir()
    (mod_dir / "meta.ini").write_text(
        "[General]\nversion=0.9\nold_key=keep_me\n[Nexus]\nnexusID=42\n",
        encoding="utf-8",
    )

    mod = MagicMock()
    mod.absolutePath.return_value = str(mod_dir)
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=5: fn()

    result = bridge._handle_mods_meta_write(
        organizer,
        pump,
        {"name": "ModA", "updates": {"General": {"version": "2.0"}}},
    )

    assert result["ok"] is True
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(mod_dir / "meta.ini", encoding="utf-8")
    assert parser["General"]["version"] == "2.0"
    assert parser["General"]["old_key"] == "keep_me"
    assert parser["Nexus"]["nexusID"] == "42"


def test_mods_meta_write_invalid_params(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    organizer = MagicMock()
    pump = MagicMock()

    result = bridge._handle_mods_meta_write(organizer, pump, {"name": "ModA"})
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_params"

    result = bridge._handle_mods_meta_write(organizer, pump, {"name": "ModA", "updates": "not a dict"})
    assert result["ok"] is False


def test_mods_meta_write_mod_not_found(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    mod_list = MagicMock()
    mod_list.getMod.return_value = None
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()

    result = bridge._handle_mods_meta_write(
        organizer,
        pump,
        {"name": "NoSuch", "updates": {"General": {"x": "y"}}},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "mod_not_found"


def test_mods_meta_write_atomic_no_leftover_tmp(monkeypatch, tmp_path):
    """Atomic write must clean up temp file after success."""

    bridge = _load_bridge(monkeypatch)

    mod_dir = tmp_path / "ModA"
    mod_dir.mkdir()
    mod = MagicMock()
    mod.absolutePath.return_value = str(mod_dir)
    mod_list = MagicMock()
    mod_list.getMod.return_value = mod
    organizer = MagicMock()
    organizer.modList.return_value = mod_list
    pump = MagicMock()
    pump.invoke_blocking.side_effect = lambda fn, timeout_s=5: fn()

    result = bridge._handle_mods_meta_write(
        organizer,
        pump,
        {"name": "ModA", "updates": {"General": {"key": "value"}}},
    )

    assert result["ok"] is True
    leftovers = list(mod_dir.glob(".tmp-*"))
    assert leftovers == []
