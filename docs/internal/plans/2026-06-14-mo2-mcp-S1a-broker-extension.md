# S1a — Broker Extension (Tasks 1-15)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extend `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` (the IPluginTool inside MO2) with a canonical envelope schema, lifecycle command (`system.shutdown`), and mobase mutator commands for mods + plugins. Each command must respect the main-thread routing matrix and emit readback fields for silent-noop detection.

**Architecture:** Existing broker uses dict-based envelope at `build_transport_response()` (`mo2_agent_control.py:292-308`). New commands register in the `_command_handlers` map (`mo2_agent_control.py:223-236`). Mutating commands route through `MainThreadCallPump` (lines 149-207). Schema lives at new `tools/mo2-control-plane/live-bridge/broker-schema.json` so S2 TS MCP and Python broker share one source of truth.

**Tech Stack:** Python 3.11+, PyQt6 (via MO2 embedded Python), Windows named pipes, JSON Schema Draft 2020-12.

---

## File Structure

- Create: `tools/mo2-control-plane/live-bridge/broker-schema.json` — canonical envelope + command catalog
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:223-236` — register new handlers
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:1269-1327` — add handler impls
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:292-308` — error code enum extension
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_envelope.py` — schema validation
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_mods_commands.py` — mods.* command tests
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_plugins_commands.py` — plugins.* command tests

Existing `mo2_agent_control.py` is 1529 lines; modifications append new handlers + handler map entries, not restructure.

---

## Task 1: Define canonical broker envelope schema

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/broker-schema.json`
- Test: `tools/mo2-control-plane/live-bridge/tests/test_broker_envelope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_broker_envelope.py
import json
from pathlib import Path
import jsonschema

SCHEMA_PATH = Path(__file__).parent.parent / "broker-schema.json"

def test_schema_loads_as_valid_json_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema["definitions"]["request"])
    jsonschema.Draft202012Validator.check_schema(schema["definitions"]["response"])

def test_valid_request_passes_validation():
    schema = json.loads(SCHEMA_PATH.read_text())
    request = {
        "protocol_version": "1",
        "request_id": "req-001",
        "session_id": "sess-abc",
        "method": "system.ping",
        "payload": {},
    }
    jsonschema.validate(request, schema["definitions"]["request"])

def test_valid_response_ok_passes():
    schema = json.loads(SCHEMA_PATH.read_text())
    response = {
        "protocol_version": "1",
        "request_id": "req-001",
        "ok": True,
        "result": {"pong": True},
        "error": None,
    }
    jsonschema.validate(response, schema["definitions"]["response"])

def test_valid_response_error_passes():
    schema = json.loads(SCHEMA_PATH.read_text())
    response = {
        "protocol_version": "1",
        "request_id": "req-001",
        "ok": False,
        "result": None,
        "error": {"code": "method_not_found", "message": "..."},
    }
    jsonschema.validate(response, schema["definitions"]["response"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/mo2-control-plane/live-bridge/tests/test_broker_envelope.py -v`
Expected: FAIL — `broker-schema.json` missing.

- [ ] **Step 3: Create schema file**

```json
// tools/mo2-control-plane/live-bridge/broker-schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "MO2 control-plane broker protocol",
  "description": "Canonical envelope schema shared between mo2_agent_control.py (Python broker inside MO2) and the TypeScript MCP server (pipe client).",
  "definitions": {
    "request": {
      "type": "object",
      "required": ["protocol_version", "request_id", "method", "payload"],
      "properties": {
        "protocol_version": {"const": "1"},
        "request_id": {"type": "string", "minLength": 1},
        "session_id": {"type": "string"},
        "method": {"type": "string", "pattern": "^[a-z]+(\\.[a-z_]+)+$"},
        "payload": {"type": "object"}
      },
      "additionalProperties": false
    },
    "response": {
      "type": "object",
      "required": ["protocol_version", "request_id", "ok"],
      "properties": {
        "protocol_version": {"const": "1"},
        "request_id": {"type": "string"},
        "ok": {"type": "boolean"},
        "result": {"type": ["object", "null"]},
        "error": {
          "type": ["object", "null"],
          "required": ["code", "message"],
          "properties": {
            "code": {"$ref": "#/definitions/errorCode"},
            "message": {"type": "string"}
          }
        }
      },
      "additionalProperties": false
    },
    "errorCode": {
      "enum": [
        "invalid_request", "method_not_found", "invalid_params",
        "transport_error", "not_implemented", "internal_error",
        "mod_not_found", "priority_out_of_range", "plugin_not_found",
        "refresh_timeout", "main_thread_unavailable", "mo2_shutting_down"
      ]
    }
  }
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tools/mo2-control-plane/live-bridge/tests/test_broker_envelope.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/mo2-control-plane/live-bridge/broker-schema.json tools/mo2-control-plane/live-bridge/tests/test_broker_envelope.py
git commit -m "feat(mo2-broker): canonical envelope schema for MCP+broker contract"
```

---

## Task 2: Extend error code enum in broker

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:292-308` (around `build_transport_response()`)

- [ ] **Step 1: Locate the existing error envelope construction**

Read lines 292-308. Confirm current shape returns `{"ok": False, "error": {"code": str, "message": str}}`.

- [ ] **Step 2: Define error code constants**

Add at top of file after imports:

```python
# Canonical error codes (match broker-schema.json#/definitions/errorCode)
class ErrorCode:
    INVALID_REQUEST = "invalid_request"
    METHOD_NOT_FOUND = "method_not_found"
    INVALID_PARAMS = "invalid_params"
    TRANSPORT_ERROR = "transport_error"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL_ERROR = "internal_error"
    MOD_NOT_FOUND = "mod_not_found"
    PRIORITY_OUT_OF_RANGE = "priority_out_of_range"
    PLUGIN_NOT_FOUND = "plugin_not_found"
    REFRESH_TIMEOUT = "refresh_timeout"
    MAIN_THREAD_UNAVAILABLE = "main_thread_unavailable"
    MO2_SHUTTING_DOWN = "mo2_shutting_down"
```

- [ ] **Step 3: Replace string literals in existing handlers**

Run: `grep -n '"code": "' tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
Replace each literal with the `ErrorCode.*` constant. Existing codes (`invalid_request` etc.) are unchanged at the wire level.

- [ ] **Step 4: Commit**

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py
git commit -m "refactor(mo2-broker): introduce ErrorCode constants matching schema"
```

---

## Task 3: Add `system.shutdown` handler (ordering-critical)

Spec trap reference: oracle traps §5.1. The response MUST be sent and flushed BEFORE `QCoreApplication.quit()` is enqueued, or the client never receives the success ack.

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:223-236` (register handler)
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py:1269-1327` (add handler impl)
- Test: `tools/mo2-control-plane/live-bridge/tests/test_broker_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_broker_lifecycle.py
def test_shutdown_response_sent_before_quit_enqueue(monkeypatch):
    """Critical: response must be flushed before quit() to avoid client timeout."""
    from mo2_agent_control import _handle_system_shutdown
    
    ordering = []
    
    class FakePump:
        def enqueue(self, callable_):
            ordering.append("quit_enqueued")
    
    class FakePipe:
        def write_response(self, _):
            ordering.append("response_written")
        def flush(self):
            ordering.append("response_flushed")
    
    pump = FakePump()
    pipe = FakePipe()
    
    _handle_system_shutdown(pump=pump, pipe=pipe, request_id="req-1")
    
    assert ordering == ["response_written", "response_flushed", "quit_enqueued"]
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `_handle_system_shutdown` not defined.

- [ ] **Step 3: Implement the handler**

```python
# Add to mo2_agent_control.py near line 1269 (with other handlers)
def _handle_system_shutdown(pump, pipe, request_id):
    """
    Ordering contract (oracle traps §5.1):
    1. Write success response to pipe
    2. Flush pipe buffer to guarantee delivery
    3. ONLY THEN enqueue QCoreApplication.quit() on main thread pump
    
    Direct quit() from background thread → Qt event loop crash.
    """
    response = {
        "protocol_version": "1",
        "request_id": request_id,
        "ok": True,
        "result": {"shutting_down": True},
        "error": None,
    }
    pipe.write_response(response)
    pipe.flush()  # KERNEL32.FlushFileBuffers in production
    
    from PyQt6.QtCore import QCoreApplication
    pump.enqueue(lambda: QCoreApplication.quit())
```

Register in `_command_handlers` map around line 226:

```python
self._command_handlers["system.shutdown"] = lambda req: _handle_system_shutdown(
    pump=self._main_thread_pump,
    pipe=self._current_pipe,
    request_id=req["request_id"],
)
```

- [ ] **Step 4: Verify test passes**

Run: `pytest tools/mo2-control-plane/live-bridge/tests/test_broker_lifecycle.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/mo2-control-plane/live-bridge/mo2_agent_control.py tools/mo2-control-plane/live-bridge/tests/test_broker_lifecycle.py
git commit -m "feat(mo2-broker): system.shutdown with response-before-quit ordering"
```

---

## Task 4: Add `mods.list` handler (background-safe)

Spec trap reference: oracle traps §2.1 — `IModList.allMods()` is a snapshot read, safe in background thread.

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` (add handler + register)
- Test: `tools/mo2-control-plane/live-bridge/tests/test_broker_mods_commands.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_broker_mods_commands.py
def test_mods_list_returns_all_mods_with_priority_enabled():
    from mo2_agent_control import _handle_mods_list
    
    class FakeOrganizer:
        def modList(self):
            class FakeModList:
                def allMods(self):
                    return ["ModA", "ModB", "Separator_separator"]
                def priority(self, name):
                    return {"ModA": 0, "ModB": 1, "Separator_separator": 2}[name]
                def state(self, name):
                    return 0x04 if "Separator" not in name else 0x10  # FLAG_ACTIVE vs FLAG_SEPARATOR
            return FakeModList()
    
    result = _handle_mods_list(organizer=FakeOrganizer(), payload={})
    
    assert result["ok"] is True
    assert len(result["result"]["mods"]) == 3
    assert result["result"]["mods"][0] == {
        "name": "ModA", "priority": 0, "enabled": True, "is_separator": False
    }
```

- [ ] **Step 2: Run test, expect fail**

- [ ] **Step 3: Implement**

```python
def _handle_mods_list(organizer, payload):
    """Background-thread safe (snapshot read of IModList.allMods())."""
    mod_list = organizer.modList()
    mods = []
    for name in mod_list.allMods():
        state = mod_list.state(name)
        mods.append({
            "name": name,
            "priority": mod_list.priority(name),
            "enabled": bool(state & 0x04),  # ModState::Active
            "is_separator": name.endswith("_separator"),
        })
    return {"ok": True, "result": {"mods": mods}, "error": None}
```

Register: `self._command_handlers["mods.list"] = lambda req: _handle_mods_list(self._organizer, req["payload"])`.

- [ ] **Step 4: Verify pass**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat(mo2-broker): mods.list returns snapshot of all mods with priority+enabled"
```

---

## Task 5: Add `mods.set_active` (single + bulk, main-thread, with readback)

Spec trap reference: oracle traps §2.1, §2.2. `setActive` mutates → main-thread. Bulk version returns count; readback per-mod is critical.

**Files:**
- Modify: `mo2_agent_control.py`
- Test: `tests/test_broker_mods_commands.py`

- [ ] **Step 1: Write failing test**

```python
def test_mods_set_active_single_with_readback(qt_app):
    from mo2_agent_control import _handle_mods_set_active
    
    state = {"ModA": False}
    class FakeMods:
        def setActive(self, name, active):
            state[name] = active
            return True
        def allMods(self): return ["ModA"]
        def state(self, name): return 0x04 if state[name] else 0x00
    
    class FakeOrganizer:
        def modList(self): return FakeMods()
    
    result = _handle_mods_set_active(
        organizer=FakeOrganizer(),
        pump=DirectPump(),  # synchronous test pump
        payload={"names": ["ModA"], "active": True},
    )
    
    assert result["ok"] is True
    assert result["result"] == {
        "requested": ["ModA"],
        "applied": ["ModA"],
        "failed": [],
        "readback": [{"name": "ModA", "active": True}],
    }

def test_mods_set_active_partial_failure_reported():
    """Bulk apply may partial-fail; per-mod readback exposes truth."""
    # Similar shape, FakeMods.setActive returns False for "ModB"
    # Expect result["failed"] == ["ModB"], result["applied"] == ["ModA"]
    ...
```

- [ ] **Step 2-3: Implement**

```python
def _handle_mods_set_active(organizer, pump, payload):
    names = payload.get("names", [])
    active = payload["active"]
    if not isinstance(names, list) or not isinstance(active, bool):
        return _error_response(ErrorCode.INVALID_PARAMS, "names: list[str], active: bool")
    
    def _on_main_thread():
        mod_list = organizer.modList()
        applied, failed = [], []
        for name in names:
            try:
                ok = mod_list.setActive(name, active)
                (applied if ok else failed).append(name)
            except Exception:
                failed.append(name)
        # Readback (oracle traps §2.1 silent-noop guard)
        readback = []
        for name in names:
            try:
                state = mod_list.state(name)
                readback.append({"name": name, "active": bool(state & 0x04)})
            except Exception:
                readback.append({"name": name, "active": None})
        return {"requested": names, "applied": applied, "failed": failed, "readback": readback}
    
    result = pump.invoke_blocking(_on_main_thread, timeout_s=10)
    return {"ok": True, "result": result, "error": None}
```

Register: main-thread required.

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.set_active single+bulk via main thread, per-mod readback"
```

---

## Task 6: Add `mods.set_priority` (main-thread, with readback)

Spec trap: silent-noop on master/non-master inversion (`librarian-alpha` confirms `setPriority` returns true even when noop).

**Files:** same pattern as Task 5.

- [ ] **Steps 1-3: Test + impl**

```python
def _handle_mods_set_priority(organizer, pump, payload):
    name = payload.get("name")
    priority = payload.get("priority")
    if not isinstance(name, str) or not isinstance(priority, int):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str, priority: int")
    
    def _main():
        mod_list = organizer.modList()
        # Validate name exists
        if mod_list.getMod(name) is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, f"mod '{name}' not found")
        # Validate priority range
        max_pri = len([m for m in mod_list.allMods() if not m.endswith("_separator")])
        if priority < 0 or priority > max_pri:
            return ("error", ErrorCode.PRIORITY_OUT_OF_RANGE, f"0..{max_pri}")
        mod_list.setPriority(name, priority)
        actual = mod_list.priority(name)
        return ("ok", {"name": name, "requested_priority": priority, "actual_priority": actual,
                       "noop": actual != priority})
    
    outcome = pump.invoke_blocking(_main, timeout_s=10)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.set_priority with readback exposing silent-noop"
```

---

## Task 7: Add `mods.rename` (main-thread, pre-sanitized)

Spec trap: oracle §A4 — bad input triggers MO2 `MessageDialog::showMessage` (GUI dialog). Pre-sanitize before calling.

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
import re

_INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def _sanitize_dir_name(name: str) -> str:
    """Mirror MO2's fixDirectoryName logic to avoid triggering Qt MessageDialog."""
    cleaned = _INVALID_PATH_CHARS.sub("", name).strip().rstrip(".")
    return cleaned

def _handle_mods_rename(organizer, pump, payload):
    old = payload.get("old_name")
    new = payload.get("new_name")
    if not isinstance(old, str) or not isinstance(new, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "old_name + new_name: str")
    
    sanitized = _sanitize_dir_name(new)
    if not sanitized:
        return _error_response(ErrorCode.INVALID_PARAMS, f"new_name '{new}' invalid after sanitize")
    
    def _main():
        mod_list = organizer.modList()
        mod = mod_list.getMod(old)
        if mod is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, f"mod '{old}' not found")
        if mod_list.getMod(sanitized) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized}' already exists")
        refreshed = mod_list.renameMod(mod, sanitized)
        return ("ok", {"old_name": old, "new_name": sanitized,
                      "name_was_sanitized": sanitized != new})
    
    outcome = pump.invoke_blocking(_main, timeout_s=15)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.rename with pre-sanitization to avoid Qt MessageDialog"
```

---

## Task 8: Add `mods.remove` (main-thread, destructive)

Spec trap: oracle §A6 — physical shellDelete. Callers should pair with `mods.create_backup` (later sidecar helper).

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_mods_remove(organizer, pump, payload):
    name = payload.get("name")
    if not isinstance(name, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str")
    
    def _main():
        mod_list = organizer.modList()
        mod = mod_list.getMod(name)
        if mod is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, name)
        ok = mod_list.removeMod(mod)
        return ("ok" if ok else "error",
                {"name": name, "removed": ok} if ok else (ErrorCode.INTERNAL_ERROR, "removeMod returned False"))
    
    outcome = pump.invoke_blocking(_main, timeout_s=30)  # filesystem delete may be slow
    if outcome[0] == "error":
        return _error_response(*outcome[1])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.remove (destructive, callers responsible for backup)"
```

---

## Task 9: Add `mods.create` (main-thread, two-step createMod+setPriority)

Spec trap: oracle §A1 — MO2 GUI does two-step (createMod default priority, then setPriority). Wrapper composes them atomically.

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_mods_create(organizer, pump, payload):
    name = payload.get("name")
    target_priority = payload.get("priority")  # optional; None = default position
    if not isinstance(name, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str")
    
    sanitized = _sanitize_dir_name(name)
    if not sanitized:
        return _error_response(ErrorCode.INVALID_PARAMS, f"name '{name}' invalid")
    
    def _main():
        mod_list = organizer.modList()
        if mod_list.getMod(sanitized) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized}' exists")
        # mobase: GuessedString wrapper expected by createMod
        from mobase import GuessedString
        new_mod = organizer.createMod(GuessedString(sanitized))
        if new_mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "createMod returned None")
        actual_name = new_mod.name()
        # Optional priority set
        result = {"name": actual_name, "created": True, "priority": mod_list.priority(actual_name)}
        if target_priority is not None:
            mod_list.setPriority(actual_name, target_priority)
            result["priority"] = mod_list.priority(actual_name)
            result["requested_priority"] = target_priority
        organizer.modDataChanged(new_mod)
        return ("ok", result)
    
    outcome = pump.invoke_blocking(_main, timeout_s=15)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.create wraps createMod+setPriority+modDataChanged"
```

---

## Task 10: Add `mods.meta_read` (background-safe)

Read mod's `meta.ini` fields. Pure file read; no main-thread needed.

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
import configparser

def _handle_mods_meta_read(organizer, payload):
    name = payload.get("name")
    if not isinstance(name, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str")
    
    mod_list = organizer.modList()
    mod = mod_list.getMod(name)
    if mod is None:
        return _error_response(ErrorCode.MOD_NOT_FOUND, name)
    
    meta_path = Path(mod.absolutePath()) / "meta.ini"
    if not meta_path.exists():
        return {"ok": True, "result": {"name": name, "meta": {}, "exists": False}, "error": None}
    
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(meta_path, encoding="utf-8")
    meta = {section: dict(parser[section]) for section in parser.sections()}
    return {"ok": True, "result": {"name": name, "meta": meta, "exists": True}, "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.meta_read background-safe meta.ini parse"
```

---

## Task 11: Add `mods.meta_write` (main-thread for refresh + atomic file write)

Spec trap: oracle §3.2 — atomic temp+rename pattern from filesystem-mcp `lib.ts:260`. Plus `modDataChanged()` notification on main thread.

**Files:** same pattern. Atomic helper inlined here; sidecar gets shared helper in S1b Task 29.

- [ ] **Steps 1-3:**

```python
import tempfile, os, shutil

def _atomic_write_text(path: Path, content: str):
    """Write content to path via temp file + atomic rename. NTFS-safe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on Windows + POSIX
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

def _handle_mods_meta_write(organizer, pump, payload):
    name = payload.get("name")
    updates = payload.get("updates")  # {section: {key: value}} merge semantics
    if not isinstance(name, str) or not isinstance(updates, dict):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str, updates: dict")
    
    mod_list = organizer.modList()
    mod = mod_list.getMod(name)
    if mod is None:
        return _error_response(ErrorCode.MOD_NOT_FOUND, name)
    
    meta_path = Path(mod.absolutePath()) / "meta.ini"
    parser = configparser.ConfigParser(interpolation=None)
    if meta_path.exists():
        parser.read(meta_path, encoding="utf-8")
    for section, fields in updates.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for k, v in fields.items():
            parser.set(section, k, str(v))
    
    from io import StringIO
    buf = StringIO()
    parser.write(buf)
    _atomic_write_text(meta_path, buf.getvalue())
    
    # Notify MO2 of metadata change (main thread)
    pump.invoke_blocking(lambda: organizer.modDataChanged(mod), timeout_s=5)
    return {"ok": True, "result": {"name": name, "updated_sections": list(updates.keys())}, "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): mods.meta_write atomic+modDataChanged notification"
```

---

## Task 12: Add `plugins.list` (background-safe)

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_plugins_list(organizer, payload):
    pl = organizer.pluginList()
    plugins = []
    for name in pl.pluginNames():
        plugins.append({
            "name": name,
            "state": int(pl.state(name)),  # PluginState enum -> int
            "priority": pl.priority(name),
            "load_order": pl.loadOrder(name),  # -1 if disabled
            "origin": pl.origin(name),  # mod name | "overwrite" | "data"
            "is_master": pl.isMasterFlagged(name),
            "is_light": pl.isLightFlagged(name),
        })
    return {"ok": True, "result": {"plugins": plugins}, "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): plugins.list with state+priority+load_order+flags"
```

---

## Task 13: Add `plugins.set_state` (main-thread, readback)

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_plugins_set_state(organizer, pump, payload):
    name = payload.get("name")
    state = payload.get("state")  # int matching PluginState enum
    if not isinstance(name, str) or not isinstance(state, int):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str, state: int")
    
    def _main():
        pl = organizer.pluginList()
        if name not in pl.pluginNames():
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, name)
        pl.setState(name, state)
        return ("ok", {"name": name, "requested_state": state, "actual_state": int(pl.state(name))})
    
    outcome = pump.invoke_blocking(_main, timeout_s=10)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): plugins.set_state with readback"
```

---

## Task 14: Add `plugins.set_priority` (main-thread, silent-noop detection)

Spec trap: `setPriority` returns true even when noop on master/non-master inversion. Readback mandatory.

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_plugins_set_priority(organizer, pump, payload):
    name = payload.get("name")
    priority = payload.get("priority")
    if not isinstance(name, str) or not isinstance(priority, int):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str, priority: int")
    
    def _main():
        pl = organizer.pluginList()
        if name not in pl.pluginNames():
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, name)
        before = pl.priority(name)
        pl.setPriority(name, priority)
        after = pl.priority(name)
        return ("ok", {
            "name": name,
            "requested_priority": priority,
            "actual_priority": after,
            "noop": after == before and before != priority,
        })
    
    outcome = pump.invoke_blocking(_main, timeout_s=10)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): plugins.set_priority with silent-noop detection"
```

---

## Task 15: Add `plugins.set_load_order` (main-thread, implicit-fallback documented)

Spec trap: `setLoadOrder(seq)` puts un-listed plugins at highest priority preserving original order. Plan must encode this.

**Files:** same pattern.

- [ ] **Steps 1-3:**

```python
def _handle_plugins_set_load_order(organizer, pump, payload):
    order = payload.get("load_order")  # list[str]
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        return _error_response(ErrorCode.INVALID_PARAMS, "load_order: list[str]")
    
    def _main():
        pl = organizer.pluginList()
        all_known = set(pl.pluginNames())
        unknown = [n for n in order if n not in all_known]
        if unknown:
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, f"unknown plugins in load_order: {unknown}")
        pl.setLoadOrder(order)
        # Readback full effective order
        effective = sorted(pl.pluginNames(), key=lambda n: pl.priority(n))
        return ("ok", {
            "requested_explicit": order,
            "effective_order": effective,
            "implicitly_appended_count": len(effective) - len(order),
        })
    
    outcome = pump.invoke_blocking(_main, timeout_s=15)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Steps 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): plugins.set_load_order with implicit-fallback readback"
```

---

## End of S1a

15 tasks land: envelope schema, error codes, system.shutdown, 8 mods.* commands, 4 plugins.* commands.

Continue in `2026-06-14-mo2-mcp-S1b-broker-organizer-and-sidecar.md`:
- Task 16-22: `profile.*`, `organizer.*`, `executables.list`, `installation.*`, broker smoke test
- Task 23-30: Python sidecar package + World cache + assets wrap + pyfomod + atomic helper + integration smoke

After S1a + S1b complete, run `requesting-code-review` skill against the full broker + sidecar substrate before moving to S2 (TS MCP server skeleton).
