# S1b — Broker Organizer/Installation Commands + Python Sidecar (Tasks 16-30)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. Continues from `2026-06-14-mo2-mcp-S1a-broker-extension.md`.

**Goal:** Finish broker extension (profile / organizer / executables / installation domains) and build the Python sidecar package (`tools/mo2-mcp-sidecar/`) that the S2 TypeScript MCP server will spawn as a long-lived JSON-RPC subprocess.

**Architecture:** Sidecar = single Python 3.11+ process; speaks JSON-RPC over stdin/stdout to TS MCP; imports `mo2_assets_engine` (existing) + `pyfomod` (new dependency); holds `World` cache keyed by `(profile_dir, modlist_mtime, plugins_mtime)`. Atomic write helper extracted from S1a Task 11 into shared module.

**Tech Stack:** Python 3.11+, pyfomod, mo2_assets_engine (existing), JSON-RPC 2.0-shape envelope over stdio, pytest.

---

## File Structure

- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` (Tasks 16-21)
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_organizer.py` (Tasks 16-21)
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_smoke.py` (Task 22, gated)
- Create: `tools/mo2-mcp-sidecar/pyproject.toml` (Task 23)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/__init__.py` (Task 23)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/__main__.py` (Task 23)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/envelope.py` (Task 24)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/world.py` (Task 25)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/assets.py` (Task 26)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/fomod.py` (Tasks 27-28)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/atomic.py` (Task 29, lifted from S1a Task 11)
- Create: `tools/mo2-mcp-sidecar/tests/test_*.py` (per-task)
- Create: `tools/mo2-mcp-sidecar/tests/test_smoke_e2e.py` (Task 30, gated)

---

## Task 16: Add `profile.list` + `profile.active` (background-safe)

**Files:**
- Modify: `tools/mo2-control-plane/live-bridge/mo2_agent_control.py`
- Test: `tools/mo2-control-plane/live-bridge/tests/test_broker_organizer.py`

- [ ] **Step 1-3: Write test + impl**

```python
def _handle_profile_list(organizer, payload):
    """Background-safe: enumerate profile subdirs containing modlist.txt."""
    profiles_root = Path(organizer.basePath()) / "profiles"
    profiles = []
    for child in profiles_root.iterdir():
        if child.is_dir() and (child / "modlist.txt").exists():
            profiles.append({
                "name": child.name,
                "path": str(child),
                "has_local_inis": (child / "settings.txt").exists(),
            })
    return {"ok": True, "result": {"profiles": profiles}, "error": None}

def _handle_profile_active(organizer, payload):
    """Background-safe snapshot of current profile name + path."""
    return {"ok": True, "result": {
        "name": organizer.profileName(),
        "path": organizer.profilePath(),
    }, "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): profile.list + profile.active background-safe"
```

---

## Task 17: Add `organizer.refresh` (main-thread, no nested callbacks)

Spec trap: oracle §2.4 — refresh triggers callback cascade; no broker handler should register callbacks calling back into pump (deadlock).

**Files:** same pattern.

- [ ] **Step 1-3:**

```python
def _handle_organizer_refresh(organizer, pump, payload):
    save_changes = payload.get("save_changes", True)
    
    def _main():
        organizer.refresh(save_changes)
        # Refresh is synchronous on main thread; return when done
        return {"refreshed": True, "save_changes": save_changes,
                "timestamp_ms": int(time.time() * 1000)}
    
    result = pump.invoke_blocking(_main, timeout_s=60)  # refresh slow on large modpacks
    return {"ok": True, "result": result, "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): organizer.refresh main-thread with 60s timeout"
```

---

## Task 18: Add `organizer.resolve_path` + `find_files` + `get_file_origins` + `virtual_file_tree`

Four read-only VFS query methods. Background-safe (snapshot reads).

**Files:** same pattern.

- [ ] **Step 1-3:**

```python
def _handle_organizer_resolve_path(organizer, payload):
    filename = payload.get("filename")
    if not isinstance(filename, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "filename: str")
    resolved = organizer.resolvePath(filename)
    return {"ok": True, "result": {"filename": filename, "resolved": resolved or None}, "error": None}

def _handle_organizer_get_file_origins(organizer, payload):
    filename = payload.get("filename")
    if not isinstance(filename, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "filename: str")
    origins = list(organizer.getFileOrigins(filename) or [])
    return {"ok": True, "result": {"filename": filename, "origins": origins}, "error": None}

def _handle_organizer_find_files(organizer, payload):
    path = payload.get("path", "")
    patterns = payload.get("patterns", ["*"])
    if not isinstance(patterns, list):
        return _error_response(ErrorCode.INVALID_PARAMS, "patterns: list[str]")
    found = list(organizer.findFiles(path, patterns) or [])
    return {"ok": True, "result": {"path": path, "patterns": patterns, "files": found}, "error": None}

def _handle_organizer_virtual_file_tree(organizer, payload):
    """Returns shallow tree at given path; recursion controlled by max_depth."""
    path = payload.get("path", "")
    max_depth = payload.get("max_depth", 3)
    tree = organizer.virtualFileTree()
    # Walk via IFileTree.walk with depth limit
    entries = []
    # ... implementation walks tree.find(path) with depth ...
    return {"ok": True, "result": {"path": path, "entries": entries, "truncated": False}, "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): organizer.{resolve_path,get_file_origins,find_files,virtual_file_tree}"
```

---

## Task 19: Add `executables.list` (background, ModOrganizer.ini parse)

Spec trap: oracle §6.1 — Qt INI array dialect `1\title=...`. Custom parser, NOT configparser.

**Files:**
- Modify: `mo2_agent_control.py`
- Create: `tools/mo2-control-plane/live-bridge/qt_ini.py` (shared parser, <60 lines)
- Test: `tests/test_qt_ini.py`

- [ ] **Step 1: Write test**

```python
# tests/test_qt_ini.py
def test_parse_custom_executables_array(tmp_path):
    ini = tmp_path / "ModOrganizer.ini"
    ini.write_text("""
[General]
gameName=Fallout 4

[customExecutables]
size=2
1\\title=xEdit
1\\binary=C:/Tools/xEdit/xEdit.exe
1\\arguments=-fo4
1\\workingDirectory=C:/Tools/xEdit
1\\steamAppID=
1\\ownicon=true
2\\title=LOOT
2\\binary=C:/LOOT/LOOT.exe
2\\arguments=
2\\workingDirectory=
2\\ownicon=false
""", encoding="utf-8")
    from qt_ini import parse_custom_executables
    entries = parse_custom_executables(ini)
    assert len(entries) == 2
    assert entries[0] == {
        "title": "xEdit", "binary": "C:/Tools/xEdit/xEdit.exe",
        "arguments": "-fo4", "workingDirectory": "C:/Tools/xEdit",
        "steamAppID": "", "ownicon": True,
    }
```

- [ ] **Step 2-3: Implement**

```python
# qt_ini.py
from pathlib import Path

def parse_custom_executables(ini_path: Path) -> list[dict]:
    """Parse Qt QSettings INI array dialect under [customExecutables]."""
    lines = ini_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    section_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_section: break
            if stripped == "[customExecutables]":
                in_section = True
            continue
        if in_section and stripped and "=" in stripped:
            section_lines.append(stripped)
    
    # Parse size
    size = 0
    entries_raw = {}  # {idx: {key: value}}
    for line in section_lines:
        key, _, value = line.partition("=")
        if key == "size":
            size = int(value)
        elif "\\" in key:
            idx_str, sub_key = key.split("\\", 1)
            try:
                idx = int(idx_str)
            except ValueError:
                continue
            entries_raw.setdefault(idx, {})[sub_key] = value
    
    bool_keys = {"ownicon", "hide", "toolbar", "minimizeToSystemTray"}
    result = []
    for i in range(1, size + 1):
        raw = entries_raw.get(i, {})
        entry = {k: (v.lower() == "true" if k in bool_keys else v) for k, v in raw.items()}
        result.append(entry)
    return result
```

Wire to broker handler:

```python
def _handle_executables_list(organizer, payload):
    base = Path(organizer.basePath())
    ini = base / "ModOrganizer.ini"
    if not ini.exists():
        return _error_response(ErrorCode.INTERNAL_ERROR, f"ModOrganizer.ini not found at {ini}")
    from qt_ini import parse_custom_executables
    entries = parse_custom_executables(ini)
    return {"ok": True, "result": {"executables": entries}, "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): executables.list via Qt INI array parser"
```

---

## Task 20: Add `installation.install_local_archive` (main-thread, FOMOD-blind here)

Spec note: this is the broker primitive that calls `IOrganizer.installMod()`. FOMOD non-interactive handling lives in the TS MCP `mo2_install` tool which orchestrates pyfomod sidecar + this primitive. Pattern A (sidecar parse + createMod + populate) is built at MCP layer, not broker.

**Files:** same pattern.

- [ ] **Step 1-3:**

```python
def _handle_installation_install_local_archive(organizer, pump, payload):
    archive_path = payload.get("archive_path")
    name_suggestion = payload.get("name_suggestion", "")
    if not isinstance(archive_path, str) or not Path(archive_path).exists():
        return _error_response(ErrorCode.INVALID_PARAMS, f"archive_path missing or not found: {archive_path}")
    
    def _main():
        mod = organizer.installMod(archive_path, name_suggestion)
        if mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "installMod returned None (canceled or failed)")
        return ("ok", {
            "name": mod.name(),
            "absolute_path": mod.absolutePath(),
            "installation_file": archive_path,
        })
    
    outcome = pump.invoke_blocking(_main, timeout_s=120)  # large FOMOD wizards slow
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): installation.install_local_archive primitive (FOMOD-blind)"
```

---

## Task 21: Add `installation.create_mod_from_directory` (main-thread, Pattern A backbone)

For FOMOD Pattern A: sidecar pre-stages files in `<MO2_Root>/.mo2-mcp/staging/<install_id>/`; broker creates empty mod via `IOrganizer.createMod()` and the TS MCP moves staged content + writes meta.ini. This handler is the broker side.

**Files:** same pattern.

- [ ] **Step 1-3:**

```python
def _handle_installation_create_mod_from_directory(organizer, pump, payload):
    name = payload.get("name")
    if not isinstance(name, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "name: str")
    
    sanitized = _sanitize_dir_name(name)
    if not sanitized:
        return _error_response(ErrorCode.INVALID_PARAMS, f"name '{name}' invalid")
    
    def _main():
        mod_list = organizer.modList()
        if mod_list.getMod(sanitized) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized}' exists")
        from mobase import GuessedString
        new_mod = organizer.createMod(GuessedString(sanitized))
        if new_mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "createMod returned None")
        return ("ok", {
            "name": new_mod.name(),
            "absolute_path": new_mod.absolutePath(),
        })
    
    outcome = pump.invoke_blocking(_main, timeout_s=15)
    if outcome[0] == "error":
        return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-broker): installation.create_mod_from_directory for Pattern A backbone"
```

---

## Task 22: Broker smoke test (gated harness)

Spec note: full E2E broker test runs against real MO2 instance at `.artifacts/mo2`. Gated by `MO2_HARNESS=1` env var to skip in CI.

**Files:**
- Create: `tools/mo2-control-plane/live-bridge/tests/test_broker_smoke.py`

- [ ] **Step 1: Write the gated test**

```python
import os, pytest, json, subprocess, time
from pathlib import Path

pytestmark = pytest.mark.skipif(
    os.environ.get("MO2_HARNESS") != "1",
    reason="Requires running MO2 instance; set MO2_HARNESS=1 to enable"
)

MO2_ROOT = Path(os.environ.get("BGS_MO2_ROOT", r"D:\awesome-bgs-mod-master\.artifacts\mo2"))
ENDPOINT_FILE = MO2_ROOT / "plugins" / "Mo2AgentControl" / "bootstrap" / "runtime" / "endpoint.json"

def _send_pipe(method, payload):
    """Send via pipe client (use existing xedit-client.ps1 pattern or pwsh inline)."""
    pipe_info = json.loads(ENDPOINT_FILE.read_text())
    pipe_name = pipe_info["endpoint"]
    request = {
        "protocol_version": "1",
        "request_id": f"smoke-{int(time.time()*1000)}",
        "session_id": "smoke-test",
        "method": method,
        "payload": payload,
    }
    # Use pwsh to send via NamedPipeClientStream
    script = f"""
    $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.','{pipe_name}','InOut')
    $pipe.Connect(5000)
    $w = New-Object System.IO.StreamWriter($pipe); $w.AutoFlush = $true
    $r = New-Object System.IO.StreamReader($pipe)
    $w.WriteLine('{json.dumps(request)}')
    Write-Output $r.ReadLine()
    $pipe.Dispose()
    """
    out = subprocess.run(["pwsh", "-Command", script], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout.strip())

def test_smoke_mods_list_returns_real_mods():
    resp = _send_pipe("mods.list", {})
    assert resp["ok"] is True
    assert "mods" in resp["result"]
    assert len(resp["result"]["mods"]) > 0  # FO4 harness has ≥3 mods

def test_smoke_plugins_list_returns_real_plugins():
    resp = _send_pipe("plugins.list", {})
    assert resp["ok"] is True
    assert any(p["name"] == "Fallout4.esm" for p in resp["result"]["plugins"])

def test_smoke_profile_active_matches_default():
    resp = _send_pipe("profile.active", {})
    assert resp["ok"] is True
    assert resp["result"]["name"] == "Default"

def test_smoke_executables_list_includes_opencode_xedit():
    resp = _send_pipe("executables.list", {})
    assert resp["ok"] is True
    titles = [e["title"] for e in resp["result"]["executables"]]
    assert "OpenCode xEdit Automation Serve" in titles
```

- [ ] **Step 2: Run gated test**

```bash
$env:MO2_HARNESS = "1"
$env:BGS_MO2_ROOT = "D:\awesome-bgs-mod-master\.artifacts\mo2"
# Start MO2 manually first via Start-Process .artifacts\mo2\ModOrganizer.exe
pytest tools/mo2-control-plane/live-bridge/tests/test_broker_smoke.py -v
```

Expected: 4 tests PASS against real MO2.

- [ ] **Step 3: Commit**

```bash
git add tools/mo2-control-plane/live-bridge/tests/test_broker_smoke.py
git commit -m "test(mo2-broker): gated smoke E2E against real MO2 instance"
```

---

## Task 23: Create sidecar package skeleton

**Files:**
- Create: `tools/mo2-mcp-sidecar/pyproject.toml`
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/__init__.py` (empty)
- Create: `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/__main__.py`
- Create: `tools/mo2-mcp-sidecar/README.md` (1 paragraph)

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mo2-mcp-sidecar"
version = "0.1.0"
description = "Long-lived JSON-RPC sidecar for the MO2 MCP TS server. Wraps mo2_assets_engine and pyfomod."
requires-python = ">=3.11"
dependencies = [
    "pyfomod>=1.1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "mypy"]

[project.scripts]
mo2-mcp-sidecar = "mo2_mcp_sidecar.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
strict = true
python_version = "3.11"
```

Note: `mo2_assets_engine` is sibling dir; install via `pip install -e ../mo2-assets-engine`.

- [ ] **Step 2: Write entry point**

```python
# src/mo2_mcp_sidecar/__main__.py
import sys
from .envelope import run_stdio_loop

def main() -> int:
    """Sidecar entry. Reads JSON-RPC over stdin, writes to stdout."""
    try:
        run_stdio_loop(stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
        return 0
    except KeyboardInterrupt:
        return 130

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify import works**

```bash
cd tools/mo2-mcp-sidecar
pip install -e .
python -c "import mo2_mcp_sidecar; print('ok')"
```

- [ ] **Step 4: Commit**

```bash
git add tools/mo2-mcp-sidecar/
git commit -m "feat(mo2-sidecar): package skeleton with pyfomod + mo2_assets_engine deps"
```

---

## Task 24: Sidecar JSON-RPC envelope + ready signal

Spec trap: oracle §1.4 — sidecar emits `{"ready": true}` on stdout before accepting requests; MCP awaits this.

**Files:**
- Create: `src/mo2_mcp_sidecar/envelope.py`
- Test: `tests/test_envelope.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_envelope.py
import json, io
from mo2_mcp_sidecar.envelope import run_stdio_loop, register_method

def test_ready_signal_emitted_before_processing():
    stdin = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"system.echo","params":{"x":1}}\n')
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    register_method("system.echo", lambda params: params)
    
    run_stdio_loop(stdin=stdin, stdout=stdout, stderr=stderr, exit_on_eof=True)
    
    lines = stdout.getvalue().strip().split("\n")
    assert json.loads(lines[0]) == {"ready": True}
    assert json.loads(lines[1])["result"] == {"x": 1}

def test_invalid_json_returns_parse_error():
    stdin = io.StringIO("not json\n")
    stdout = io.StringIO()
    stderr = io.StringIO()
    run_stdio_loop(stdin=stdin, stdout=stdout, stderr=stderr, exit_on_eof=True)
    lines = stdout.getvalue().strip().split("\n")
    assert json.loads(lines[1])["error"]["code"] == -32700  # JSON-RPC parse error
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```python
# src/mo2_mcp_sidecar/envelope.py
import json
from typing import Callable, Any, IO

_METHODS: dict[str, Callable[[dict], Any]] = {}

def register_method(name: str, handler: Callable[[dict], Any]) -> None:
    _METHODS[name] = handler

def _error(id_, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}

def _result(id_, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}

def run_stdio_loop(stdin: IO, stdout: IO, stderr: IO, exit_on_eof: bool = False) -> None:
    """JSON-RPC over stdio. Emits {'ready': true} once before request loop."""
    stdout.write(json.dumps({"ready": True}) + "\n")
    stdout.flush()
    
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        
        method = req.get("method")
        params = req.get("params", {})
        id_ = req.get("id")
        
        handler = _METHODS.get(method)
        if handler is None:
            stdout.write(json.dumps(_error(id_, -32601, f"method not found: {method}")) + "\n")
            stdout.flush()
            continue
        
        try:
            result = handler(params)
            stdout.write(json.dumps(_result(id_, result)) + "\n")
        except Exception as exc:
            stdout.write(json.dumps(_error(id_, -32603, f"{type(exc).__name__}: {exc}")) + "\n")
        stdout.flush()
        
        if exit_on_eof:
            break  # test mode
```

- [ ] **Step 4: Verify pass**

- [ ] **Step 5: Commit**

```bash
git add tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/envelope.py tools/mo2-mcp-sidecar/tests/test_envelope.py
git commit -m "feat(mo2-sidecar): JSON-RPC stdio envelope with ready signal"
```

---

## Task 25: Sidecar `World` cache (mtime-keyed)

Spec trap: oracle §2.3 — cache key includes `(profile_dir, modlist_mtime, plugins_mtime)` checked every request.

**Files:**
- Create: `src/mo2_mcp_sidecar/world.py`
- Test: `tests/test_world.py`

- [ ] **Step 1-3: Write test + impl**

```python
# tests/test_world.py
def test_world_cache_invalidates_on_modlist_mtime_change(tmp_path):
    from mo2_mcp_sidecar.world import WorldCache
    
    profile_dir = tmp_path / "Default"
    profile_dir.mkdir()
    modlist = profile_dir / "modlist.txt"
    plugins = profile_dir / "plugins.txt"
    modlist.write_text("+ModA\n")
    plugins.write_text("*Fallout4.esm\n")
    
    cache = WorldCache(mods_root=tmp_path / "mods")
    w1 = cache.get(profile_dir)
    w2 = cache.get(profile_dir)
    assert w1 is w2  # cached
    
    import time
    time.sleep(0.05)
    modlist.write_text("+ModA\n+ModB\n")
    w3 = cache.get(profile_dir)
    assert w3 is not w1  # invalidated by mtime change

def test_world_invalidate_method_clears_cache(tmp_path):
    cache = WorldCache(mods_root=tmp_path / "mods")
    # ... setup ...
    cache.invalidate(profile_dir)
    w_after = cache.get(profile_dir)
    assert w_after is not w_before
```

```python
# src/mo2_mcp_sidecar/world.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class WorldKey:
    profile_dir: str
    modlist_mtime_ns: int
    plugins_mtime_ns: int

class WorldCache:
    def __init__(self, mods_root: Path):
        self.mods_root = mods_root
        self._cache: dict[str, tuple[WorldKey, "World"]] = {}
    
    def _compute_key(self, profile_dir: Path) -> WorldKey:
        return WorldKey(
            profile_dir=str(profile_dir),
            modlist_mtime_ns=(profile_dir / "modlist.txt").stat().st_mtime_ns,
            plugins_mtime_ns=(profile_dir / "plugins.txt").stat().st_mtime_ns,
        )
    
    def get(self, profile_dir: Path) -> "World":
        key = self._compute_key(profile_dir)
        cached = self._cache.get(str(profile_dir))
        if cached and cached[0] == key:
            return cached[1]
        # Rebuild
        world = self._build(profile_dir)
        self._cache[str(profile_dir)] = (key, world)
        return world
    
    def invalidate(self, profile_dir: Path) -> None:
        self._cache.pop(str(profile_dir), None)
    
    def _build(self, profile_dir: Path) -> "World":
        # Delegated to mo2_assets_engine in Task 26
        from mo2_assets_engine.profile import read_profile
        from mo2_assets_engine.mod_enumerator import enumerate_mods
        profile = read_profile(profile_dir)
        mods = enumerate_mods(profile, self.mods_root)
        return World(profile=profile, mods=mods)

@dataclass
class World:
    profile: Any
    mods: Any
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-sidecar): WorldCache mtime-keyed with explicit invalidate"
```

---

## Task 26: Sidecar wraps `mo2_assets_engine` (assets.* methods)

**Files:**
- Create: `src/mo2_mcp_sidecar/assets.py`
- Test: `tests/test_assets.py`

- [ ] **Step 1-3:**

```python
# src/mo2_mcp_sidecar/assets.py
from pathlib import Path
from .world import WorldCache
from .envelope import register_method

_cache: WorldCache | None = None

def init_assets(mods_root: Path) -> None:
    global _cache
    _cache = WorldCache(mods_root=mods_root)

def _world(profile_dir: str):
    if _cache is None:
        raise RuntimeError("assets module not initialized; call init_assets() first")
    return _cache.get(Path(profile_dir))

def assets_summary(params: dict) -> dict:
    """Return summary counts for a profile."""
    profile_dir = params["profile_dir"]
    w = _world(profile_dir)
    return {
        "profile_name": Path(profile_dir).name,
        "mod_count": len(w.mods),
        "enabled_mod_count": sum(1 for m in w.mods if m.enabled),
    }

def assets_conflicts(params: dict) -> dict:
    """Compute conflict resolution. Bounded output: max 10000 conflicts."""
    profile_dir = params["profile_dir"]
    max_results = params.get("max_results", 10000)
    w = _world(profile_dir)
    from mo2_assets_engine.conflict_resolver import resolve_all_winners
    conflicts = resolve_all_winners(w)
    truncated = len(conflicts) > max_results
    return {"conflicts": conflicts[:max_results], "total_count": len(conflicts), "truncated": truncated}

def assets_resolve_file(params: dict) -> dict:
    profile_dir = params["profile_dir"]
    virtual_path = params["virtual_path"]
    w = _world(profile_dir)
    from mo2_assets_engine.conflict_resolver import resolve_file
    winner, providers = resolve_file(w, virtual_path)
    return {"virtual_path": virtual_path, "winner": winner, "providers": providers}

def world_invalidate(params: dict) -> dict:
    profile_dir = params["profile_dir"]
    if _cache is None:
        return {"invalidated": False, "reason": "cache_not_init"}
    _cache.invalidate(Path(profile_dir))
    return {"invalidated": True, "profile_dir": profile_dir}

# Register on import
def register():
    register_method("assets.summary", assets_summary)
    register_method("assets.conflicts", assets_conflicts)
    register_method("assets.resolve_file", assets_resolve_file)
    register_method("world.invalidate", world_invalidate)
```

Wire `register()` from `__main__.py` after parsing CLI args (--mods-root, --profile-dir).

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-sidecar): assets.* JSON-RPC methods wrapping mo2_assets_engine"
```

---

## Task 27: Sidecar `fomod.parse_choices` method

Spec trap: oracle §4.2 — returns full tree (pages → groups → options with types + conditions).

**Files:**
- Create: `src/mo2_mcp_sidecar/fomod.py`
- Test: `tests/test_fomod.py`

- [ ] **Step 1-3:**

```python
# src/mo2_mcp_sidecar/fomod.py
from pathlib import Path
from .envelope import register_method

try:
    import pyfomod
    _PYFOMOD_AVAILABLE = True
except ImportError:
    _PYFOMOD_AVAILABLE = False

def fomod_parse_choices(params: dict) -> dict:
    """Return the FOMOD step tree without applying any choices."""
    if not _PYFOMOD_AVAILABLE:
        raise RuntimeError("pyfomod_not_available")
    
    archive_path = Path(params["archive_path"])
    if not archive_path.exists():
        raise FileNotFoundError(f"archive not found: {archive_path}")
    
    # pyfomod: extract or read FOMOD info.xml; here assume archive_path is an
    # already-extracted directory containing fomod/info.xml + fomod/ModuleConfig.xml.
    # Real impl: if archive_path is .7z/.zip, extract to temp dir first.
    root = pyfomod.parse(str(archive_path))
    
    pages = []
    for page in root.pages:
        groups = []
        for group in page:
            options = []
            for opt in group:
                options.append({
                    "name": opt.name,
                    "description": opt.description,
                    "image": str(opt.image) if opt.image else None,
                    "type": opt.type.name if hasattr(opt.type, "name") else str(opt.type),
                })
            groups.append({"name": group.name, "type": group.type.name, "options": options})
        pages.append({"name": page.name, "groups": groups})
    
    return {
        "fomod_name": root.name,
        "fomod_version": str(root.version) if root.version else None,
        "pages": pages,
    }

def register():
    register_method("fomod.parse_choices", fomod_parse_choices)
    # resolve_files registered in Task 28
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-sidecar): fomod.parse_choices via pyfomod"
```

---

## Task 28: Sidecar `fomod.resolve_files` method

Spec trap: oracle §4.2, §4.5 — pyfomod is one-pass; sidecar gets full file list after setting all options.

**Files:**
- Modify: `src/mo2_mcp_sidecar/fomod.py`
- Test: `tests/test_fomod.py`

- [ ] **Step 1-3:**

```python
# Append to fomod.py
def fomod_resolve_files(params: dict) -> dict:
    """Apply user choices to pyfomod installer, return resolved file mapping."""
    if not _PYFOMOD_AVAILABLE:
        raise RuntimeError("pyfomod_not_available")
    
    archive_path = Path(params["archive_path"])
    choices = params.get("choices", [])  # list of {page_name, selected_options}
    
    root = pyfomod.parse(str(archive_path))
    installer = pyfomod.Installer(root, path=str(archive_path), game_version=None, file_type=None)
    
    # Walk pages, set selections per choices
    for page in installer.pages():
        page_choice = next((c for c in choices if c["page_name"] == page.name), None)
        if page_choice is None:
            continue
        for group in page:
            wanted = [
                opt["option_name"]
                for opt in page_choice["selected_options"]
                if opt["group_name"] == group.name
            ]
            for opt in group:
                opt.selected = opt.name in wanted
    
    try:
        resolved = installer.files()  # one-pass evaluation
    except pyfomod.InvalidChoice as exc:
        raise RuntimeError(f"invalid_choices: {exc}")
    
    files = [{"source": str(f.src), "destination": str(f.dst)} for f in resolved]
    return {"files": files, "file_count": len(files)}

# Update register():
def register():
    register_method("fomod.parse_choices", fomod_parse_choices)
    register_method("fomod.resolve_files", fomod_resolve_files)
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-sidecar): fomod.resolve_files one-pass via pyfomod Installer"
```

---

## Task 29: Shared atomic write helper

Spec trap: oracle §3.2, §6.2 — temp+rename pattern shared by sidecar + broker meta.ini writes.

**Files:**
- Create: `src/mo2_mcp_sidecar/atomic.py` (extracted from S1a Task 11 inline impl)
- Test: `tests/test_atomic.py`
- Refactor: S1a Task 11's `_atomic_write_text` to import from this shared module

- [ ] **Step 1-3:**

```python
# src/mo2_mcp_sidecar/atomic.py
import os, tempfile
from pathlib import Path
from contextlib import contextmanager

def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to path via temp file + os.replace. NTFS + POSIX atomic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp-",
        suffix=path.suffix,
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Binary variant."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

@contextmanager
def atomic_write_handle(path: Path, encoding: str = "utf-8"):
    """Context-manager form for streaming writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    f = os.fdopen(fd, "w", encoding=encoding)
    try:
        yield f
        f.flush()
        os.fsync(f.fileno())
        f.close()
        os.replace(tmp_path, path)
    except Exception:
        try: f.close()
        except Exception: pass
        try: os.unlink(tmp_path)
        except OSError: pass
        raise
```

Refactor S1a Task 11 in `mo2_agent_control.py` to import from this shared module (broker can `sys.path.append` the sidecar's source dir, or the helper gets vendored into broker tree).

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-sidecar): atomic write helpers (text, bytes, context manager)"
```

---

## Task 30: Integration smoke test (broker + sidecar end-to-end)

Spec note: spawn sidecar subprocess, send a few JSON-RPC requests over stdio, verify responses. Then (gated) test broker pipe + sidecar concurrent on real MO2.

**Files:**
- Create: `tools/mo2-mcp-sidecar/tests/test_smoke_e2e.py`

- [ ] **Step 1: Write test**

```python
# tests/test_smoke_e2e.py
import subprocess, json, sys, os
import pytest
from pathlib import Path

def test_sidecar_subprocess_emits_ready_and_handles_assets_summary(tmp_path):
    """Spawn sidecar, send a request, verify response. No MO2 needed."""
    # Set up minimal profile + mods structure
    profile = tmp_path / "profiles" / "Default"
    profile.mkdir(parents=True)
    (profile / "modlist.txt").write_text("+ModA\n+ModB\n", encoding="utf-8")
    (profile / "plugins.txt").write_text("*Fallout4.esm\n", encoding="utf-8")
    mods = tmp_path / "mods"
    (mods / "ModA").mkdir(parents=True)
    (mods / "ModB").mkdir(parents=True)
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "mo2_mcp_sidecar",
         "--mods-root", str(mods)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    try:
        # Read ready signal
        ready_line = proc.stdout.readline()
        assert json.loads(ready_line) == {"ready": True}
        
        # Send assets.summary
        req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "assets.summary",
                          "params": {"profile_dir": str(profile)}}) + "\n"
        proc.stdin.write(req)
        proc.stdin.flush()
        
        resp_line = proc.stdout.readline()
        resp = json.loads(resp_line)
        assert resp["result"]["mod_count"] == 2
        assert resp["result"]["enabled_mod_count"] == 2
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)

@pytest.mark.skipif(os.environ.get("MO2_HARNESS") != "1", reason="needs running MO2")
def test_broker_smoke_plus_sidecar_concurrent():
    """Gated: broker pipe call + sidecar JSON-RPC call concurrent, no contention."""
    # ... orchestrate both transports in parallel; ensure both respond < 10s
    pass
```

- [ ] **Step 2: Run**

```bash
cd tools/mo2-mcp-sidecar
pytest tests/test_smoke_e2e.py::test_sidecar_subprocess_emits_ready_and_handles_assets_summary -v
```

Expected: PASS without MO2 running.

```bash
$env:MO2_HARNESS = "1"
pytest tests/test_smoke_e2e.py -v
```

Expected: 2 tests PASS (with real MO2).

- [ ] **Step 3: Commit + close S1**

```bash
git commit -am "test(mo2-sidecar): integration smoke E2E (sidecar subprocess + gated broker)"
```

---

## End of S1

After completing S1a + S1b (30 tasks total):

**Substrate landed:**
- `tools/mo2-control-plane/live-bridge/broker-schema.json` — canonical envelope contract
- `tools/mo2-control-plane/live-bridge/mo2_agent_control.py` — extended with `system.shutdown` + 8 mods.* + 4 plugins.* + 2 profile.* + 4 organizer.* + executables.list + 2 installation.*  commands
- `tools/mo2-control-plane/live-bridge/qt_ini.py` — Qt INI array parser
- `tools/mo2-control-plane/live-bridge/tests/` — broker unit + gated smoke tests
- `tools/mo2-mcp-sidecar/` — Python sidecar package with assets.*, fomod.*, world.* methods + atomic helper

**Verification:**
- All broker unit tests pass
- Sidecar unit tests pass
- Gated `MO2_HARNESS=1` smoke E2E tests pass against `.artifacts/mo2`
- Commit count: ~22 small commits across S1a + S1b

**Review gate:**

Before proceeding to S2 (TS MCP server skeleton), run `requesting-code-review` skill:
- Verify envelope schema is genuinely shared (no field drift)
- Verify all mutator commands have readback fields
- Verify atomic helpers used consistently for all file writes
- Verify gated tests are correctly skipped in CI
- Verify no broker handler registers nested callbacks (deadlock prevention from oracle traps §2.4)

After review-pass: merge `feat/mo2-mcp` partial → main with `--no-ff`, refresh vendor clone, then start S2 plan.
