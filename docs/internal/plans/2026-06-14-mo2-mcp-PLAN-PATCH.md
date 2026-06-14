# PLAN-PATCH (oracle-alpha BLOCKER fixes for v1)

> **Read before any S1-S5 implementation.** This patch supersedes conflicting sections in plan files. Apply via fixer's first action: re-read PLAN-PATCH for the relevant Task, then proceed to the plan's other Steps.

## P-B1 — PipeClient model: one connection per call (replaces S2a Task S2.7)

In `src/pipe-client.ts`, replace the persistent-socket implementation with one connection per call:

```typescript
import { connect } from "node:net";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export interface BrokerResponse { ok: boolean; result?: any; error?: { code: string; message: string }; }

export class PipeClient {
  private pipeName?: string;
  private connectedOnce = false;

  async discoverAndConnect(mo2Root: string, _timeoutMs = 5000): Promise<void> {
    const endpoint = JSON.parse(await readFile(
      join(mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime", "endpoint.json"), "utf8"));
    this.pipeName = endpoint.endpoint;
    // Smoke-test with a ping; broker disconnects after — that's the contract
    await this.call("system.ping", {});
    this.connectedOnce = true;
  }

  async call(method: string, payload: Record<string, unknown>, timeoutMs = 30000): Promise<BrokerResponse> {
    if (!this.pipeName) throw new Error("pipe not discovered");
    const id = `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const req = { protocol_version: "1", request_id: id, session_id: "mo2-mcp", method, payload };
    const path = `\\\\.\\pipe\\${this.pipeName.replace(/^\\\\\.\\pipe\\/, "")}`;

    return new Promise<BrokerResponse>((resolve, reject) => {
      const sock = connect(path);
      let buffer = "";
      const timer = setTimeout(() => { sock.destroy(); reject(new Error("pipe call timeout")); }, timeoutMs);

      sock.once("connect", () => sock.write(JSON.stringify(req) + "\n"));
      sock.on("data", chunk => { buffer += chunk.toString("utf8"); });
      sock.on("close", () => {
        clearTimeout(timer);
        const line = buffer.split("\n")[0];
        if (!line) return reject(new Error("empty pipe response"));
        try { resolve(JSON.parse(line)); } catch (e) { reject(e); }
      });
      sock.once("error", err => { clearTimeout(timer); reject(err); });
    });
  }

  isConnected(): boolean { return this.connectedOnce; }
  close(): void { this.connectedOnce = false; }
}
```

**Why:** Broker's `serve_named_pipe_client` handles one request then disconnects (`DisconnectNamedPipe` + `CloseHandle` at line 699 of `mo2_agent_control.py`). Persistent socket model doesn't match contract.

## P-B2 — `system.shutdown` ordering via post-response hooks (replaces S1a Task 3)

Add to `mo2_agent_control.py` before existing handler registrations:

```python
# Post-response hook registry (FIFO per-request, fires after pipe response is written + flushed)
_post_response_hooks: list = []

def register_post_response_hook(callable_):
    _post_response_hooks.append(callable_)

def drain_post_response_hooks():
    while _post_response_hooks:
        hook = _post_response_hooks.pop(0)
        try: hook()
        except Exception as e: log.warning(f"post-response hook error: {e}")
```

Modify `serve_named_pipe_client` (around line 690-700) to call `drain_post_response_hooks()` AFTER `FlushFileBuffers` + BEFORE `DisconnectNamedPipe`.

The `system.shutdown` handler then becomes:

```python
def _handle_system_shutdown(organizer, payload):
    """Return ok response; queue Qt quit as post-response hook so client gets ACK first."""
    from PyQt6.QtCore import QCoreApplication
    pump = _get_main_thread_pump()
    register_post_response_hook(lambda: pump.enqueue(lambda: QCoreApplication.quit()))
    return {"ok": True, "result": {"shutting_down": True}, "error": None}
```

Test (Task 3 Step 1) updated:
```python
def test_shutdown_response_written_and_hook_queued():
    from mo2_agent_control import _handle_system_shutdown, _post_response_hooks
    _post_response_hooks.clear()
    response = _handle_system_shutdown(organizer=None, payload={})
    assert response["ok"] is True
    assert response["result"]["shutting_down"] is True
    assert len(_post_response_hooks) == 1  # quit hook queued for after-response
```

**Why:** Handlers return dicts; pipe write happens in `serve_named_pipe_client`. Direct `pipe.flush()` from handler races the response write.

## P-B3 — `routeToPlanApply` helper (added to S2b Task S2.13)

Append to `src/plan-apply.ts`:

```typescript
export async function routeToPlanApply(
  handler: PlanApplyHandler, args: any, ctx: ToolContext
): Promise<any> {
  if (args.mode === "plan") {
    return runPlanMode(handler, args, ctx, ctx.plans, ctx.snapshots);
  }
  if (args.mode === "apply") {
    return runApplyMode(handler, args, ctx, ctx.plans);
  }
  throw new Error(`invalid mode: ${args.mode} (must be "plan" or "apply")`);
}
```

(Depends on `ToolContext` carrying `plans` + `snapshots` — see P-F9 below.)

## P-B4 — TypeScript `atomic.ts` (new Task S2.4.5)

Create `src/atomic.ts`:

```typescript
import { mkdir, rename, writeFile } from "node:fs/promises";
import { dirname, join, basename, extname } from "node:path";
import { randomBytes } from "node:crypto";

export async function atomicWriteText(path: string, content: string, encoding: BufferEncoding = "utf8"): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const ext = extname(path);
  const tmp = join(dirname(path), `.tmp-${randomBytes(6).toString("hex")}${ext}`);
  await writeFile(tmp, content, encoding);
  await rename(tmp, path);  // atomic on NTFS + POSIX
}

export async function atomicWriteBytes(path: string, content: Buffer): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const ext = extname(path);
  const tmp = join(dirname(path), `.tmp-${randomBytes(6).toString("hex")}${ext}`);
  await writeFile(tmp, content);
  await rename(tmp, path);
}
```

Test: write to file, kill mid-write (kill the process), verify either old content or new content but never partial.

Insert as Task **S2.4.5** between S2a Task S2.4 (MO ini parser) and Task S2.5 (profile reader).

## P-B5 — New broker commands `organizer.start_application` + `organizer.wait_for_application` (S1b)

Insert as Tasks **S1b.18.5a** and **S1b.18.5b** after S1b Task 18.

### `organizer.start_application` (main-thread)
```python
def _handle_organizer_startApplication(organizer, pump, payload):
    name_or_path = payload.get("executable")
    args_list = payload.get("args", [])
    cwd = payload.get("cwd", "")
    profile = payload.get("profile", "")
    forced_overwrite = payload.get("forcedCustomOverwrite", "")
    ignore_overwrite = payload.get("ignoreCustomOverwrite", False)
    if not isinstance(name_or_path, str):
        return _error_response(ErrorCode.INVALID_PARAMS, "executable: str")

    def _main():
        handle = organizer.startApplication(name_or_path, args_list, cwd, profile,
                                            forced_overwrite, ignore_overwrite)
        if handle == 0:
            return ("error", ErrorCode.INTERNAL_ERROR, "startApplication returned 0 (launch failed)")
        return ("ok", {"handle": handle, "executable": name_or_path})

    outcome = pump.invoke_blocking(_main, timeout_s=15)
    if outcome[0] == "error": return _error_response(outcome[1], outcome[2])
    return {"ok": True, "result": outcome[1], "error": None}
```

### `organizer.wait_for_application` (main-thread; auto_refresh=True default)
```python
def _handle_organizer_waitForApplication(organizer, pump, payload):
    handle = payload.get("handle")
    refresh = payload.get("refresh", True)
    if not isinstance(handle, int):
        return _error_response(ErrorCode.INVALID_PARAMS, "handle: int")

    def _main():
        success, exit_code = organizer.waitForApplication(handle, refresh)
        return ("ok", {"handle": handle, "success": success, "exit_code": exit_code})

    outcome = pump.invoke_blocking(_main, timeout_s=3600)  # game runs may be hours
    return {"ok": True, "result": outcome[1], "error": None}
```

Register both as main-thread-required. Update `broker-schema.json` method-pattern accepts these.

## P-B6 — New sidecar methods `archive.extract_all`, `install.conflict_preview`, `install.stage_fomod` (S1b)

Insert as Tasks **S1b.28.5a/b/c** after S1b Task 28.

### `archive.extract_all` (in `src/mo2_mcp_sidecar/archive.py`, new file)
```python
import zipfile
from pathlib import Path
from .envelope import register_method
try:
    import py7zr; _PY7ZR = True
except ImportError: _PY7ZR = False

def archive_extract_all(params: dict) -> dict:
    archive_path = Path(params["archive_path"])
    dest = Path(params["dest"])
    if not archive_path.exists(): raise FileNotFoundError(str(archive_path))
    dest.mkdir(parents=True, exist_ok=True)
    suffix = archive_path.suffix.lower()
    extracted = []
    if suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest)
            extracted = zf.namelist()
    elif suffix in (".7z", ".rar") and _PY7ZR:
        with py7zr.SevenZipFile(archive_path) as z:
            z.extractall(dest)
            extracted = list(z.getnames())
    else:
        raise RuntimeError(f"unsupported_archive_format: {suffix}")
    return {"files": extracted, "file_count": len(extracted), "dest": str(dest)}

def register():
    register_method("archive.extract_all", archive_extract_all)
```

Add `py7zr` to `pyproject.toml` dependencies.

### `install.conflict_preview` (in `src/mo2_mcp_sidecar/install.py`, new file)
```python
from pathlib import Path
from .envelope import register_method
from .world import WorldCache, World

def install_conflict_preview(params: dict) -> dict:
    """Preview which files of the staged content will conflict with current enabled mods at the requested priority."""
    profile_dir = Path(params["profile_dir"])
    staged_files = params["staged_files"]  # list of {source, destination} or list of relative paths
    target_priority = params["target_priority"]  # "top"|"bottom"|int
    cache: WorldCache = params["_cache_ref"]  # injected by register_with_cache below
    w = cache.get(profile_dir)
    # Convert staged files to a synthetic Mod entry with desired priority
    rel_paths = [f.get("destination") if isinstance(f, dict) else f for f in staged_files]
    synthetic_mod_files = set(rel_paths)
    conflicts = []
    for existing_mod in w.mods:
        # Compute intersection of files
        if existing_mod.files & synthetic_mod_files:  # assumes Mod has files: set
            overlap = sorted(existing_mod.files & synthetic_mod_files)
            conflicts.append({"with_mod": existing_mod.name, "shared_files": overlap[:50], "shared_count": len(overlap)})
    summary = f"{sum(c['shared_count'] for c in conflicts)} overlapping files across {len(conflicts)} existing mods"
    return {"summary": summary, "conflicts": conflicts}

def register_with_cache(cache: WorldCache):
    register_method("install.conflict_preview", lambda p: install_conflict_preview({**p, "_cache_ref": cache}))
```

### `install.stage_fomod` (in `install.py`)
```python
def install_stage_fomod(params: dict) -> dict:
    """Combine fomod.resolve_files + extract resolved files to staging dir."""
    from .fomod import fomod_resolve_files
    archive_path = Path(params["archive_path"])
    choices = params["choices"]
    staging_dir = Path(params["staging_dir"])
    resolved = fomod_resolve_files({"archive_path": str(archive_path), "choices": choices})
    # Extract resolved files only (not whole archive)
    staging_dir.mkdir(parents=True, exist_ok=True)
    # Implementation: use py7zr/zipfile with filter on resolved["files"]
    # For each {source, destination}: extract source into staging_dir/destination
    file_count = 0
    if archive_path.suffix.lower() in (".7z", ".rar"):
        import py7zr
        with py7zr.SevenZipFile(archive_path) as z:
            wanted = {f["source"] for f in resolved["files"]}
            names = z.getnames()
            for name in names:
                if name in wanted:
                    z.extract(targets=[name], path=str(staging_dir))
                    # Move to destination path
                    src = staging_dir / name
                    dest = staging_dir / next(f["destination"] for f in resolved["files"] if f["source"] == name)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    src.rename(dest)
                    file_count += 1
    return {"staging_dir": str(staging_dir), "file_count": file_count, "files": resolved["files"]}

# Update register_with_cache to also register stage_fomod
```

## P-B7 — `--game` propagation to sidecar (S1b Task 23-24 amendment)

In `tools/mo2-mcp-sidecar/src/mo2_mcp_sidecar/__main__.py`, accept `--game`:

```python
import argparse, sys
from pathlib import Path
from .envelope import run_stdio_loop
from .assets import init_assets, register as register_assets
from .archive import register as register_archive
from .install import register_with_cache as register_install
from .fomod import register as register_fomod
from .world import WorldCache

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mods-root", required=True, type=Path)
    parser.add_argument("--profile-dir", required=False, type=Path, default=None)
    parser.add_argument("--game", required=True,
        choices=["FALLOUT4", "SKYRIM_SE", "SKYRIM_LE", "STARFIELD", "OBLIVION", "FALLOUT_NV"])
    args = parser.parse_args()
    
    cache = WorldCache(mods_root=args.mods_root, game=args.game)
    init_assets(cache=cache, game=args.game)
    register_assets(); register_archive(); register_fomod()
    register_install(cache)
    
    return run_stdio_loop(sys.stdin, sys.stdout, sys.stderr)

if __name__ == "__main__":
    sys.exit(main())
```

In MCP bootstrap (S2b Task S2.14) before sidecar spawn:
```typescript
const gameMap: Record<string, string> = {
  "fallout4": "FALLOUT4", "skyrimSE": "SKYRIM_SE", "skyrimLE": "SKYRIM_LE",
  "starfield": "STARFIELD", "oblivion": "OBLIVION", "falloutNV": "FALLOUT_NV",
};
const gameUpper = gameMap[ini.general.game!] ?? "FALLOUT4";
await sidecar.start({
  modsRoot: ini.settings.modDirectory ?? join(mo2Root, "mods"),
  profileDir, game: gameUpper,
});
```

Update `SidecarClient.start()` (S2b Task S2.8) to pass `--game`:
```typescript
this.proc = spawn(python, ["-m", "mo2_mcp_sidecar",
  "--mods-root", opts.modsRoot, "--profile-dir", opts.profileDir, "--game", opts.game], ...);
```

Update `WorldCache.__init__` (S1b Task 25) to accept and store `game`. Pass to `discover_archives_for_plugins` calls.

## FIX-DURING-IMPL patches (lighter touch — fixers handle naturally)

### P-F1 / P-F2 — Shared helpers (`src/path-helpers.ts` + `src/ini-helpers.ts`)
First S4 fixer (S4.1) creates both helper files. Subsequent S4/S5 fixers import.

```typescript
// src/path-helpers.ts
import { readMoIni } from "./mo-ini.js";
import { join } from "node:path";

export async function resolveModMetaPath(modName: string, ctx: { config: { mo2Root: string } }): Promise<string> {
  const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
  const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
  return join(modsDir, modName, "meta.ini");
}
```

```typescript
// src/ini-helpers.ts
export function upsertIniValue(text: string, section: string, key: string, value: string): string {
  // (full impl from S4.1 Task)
}
```

### P-F3 — `organizer.virtual_file_tree` real impl
S1b Task 18 fixer implements `IFileTree.walk` with depth-limit + `WalkReturn` handling. Spec: walk returns list of `{path, type: "file"|"directory", origin_mod: str | null}` entries up to `max_depth`.

### P-F4 — Use mobase `ModState` import
S1a Task 4 (and all `*.list` handlers):
```python
try:
    from mobase import ModState
    _ACTIVE_FLAG = int(ModState.ACTIVE)
except ImportError:
    _ACTIVE_FLAG = 2  # fallback for unit tests; runtime value verified above
```

### P-F5 — Prefer API over naming when live
S1a Task 4: when `organizer` is not None, use `mod_list.getMod(name).isSeparator()`. Fall back to `name.endswith("_separator")` only for offline TS profile reader (S2.5).

### P-F6 — `profile.initialize` broker command (S1b new task)
Add `profile.initialize` between Tasks 16-17:
```python
def _handle_profile_initialize(organizer, pump, payload):
    profile_dir = payload["profile_dir"]
    settings_list = payload.get("settings", ["MODS", "CONFIGURATION"])
    
    def _main():
        from mobase import ProfileSetting
        plugin_game = organizer.managedGame()
        flags = 0
        for s in settings_list:
            flags |= int(getattr(ProfileSetting, s))
        from PyQt6.QtCore import QDir
        plugin_game.initializeProfile(QDir(profile_dir), flags)
        return ("ok", {"profile_dir": profile_dir, "settings_applied": settings_list})
    
    outcome = pump.invoke_blocking(_main, timeout_s=30)
    return {"ok": True, "result": outcome[1], "error": None}
```

### P-F7 — `ToolContext` mutable for pipe swap
Already a class instance in bootstrap; ensure no `Object.freeze`. Document `mo2_switch_profile` as authorized in-place mutator of `ctx.pipeClient`.

### P-F8 — MCP smoke test uses correct JSON-RPC
S2b Task S2.15:
```typescript
const req = { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} };
proc.stdin.write(JSON.stringify(req) + "\n");
const resp = JSON.parse((await firstLine(proc.stdout)).toString());
expect(resp.result.tools).toEqual([]);
```

### P-F9 — `ToolContext` carries cache + snapshots + audit
S2b Task S2.14 bootstrap:
```typescript
const ctx: ToolContext = {
  config, pipeClient: pipe.isConnected() ? pipe : undefined,
  sidecar: sidecar.isReady() ? sidecar : undefined,
  sessionId, plans, snapshots, audit,
};
```

### P-F10 — Sidecar `WorldCache` lock for concurrent builds
S1b Task 25 `world.py`:
```python
import threading

class WorldCache:
    def __init__(self, mods_root: Path, game: str):
        self.mods_root = mods_root; self.game = game
        self._cache: dict[str, tuple[WorldKey, World]] = {}
        self._build_locks: dict[str, threading.Lock] = {}
    
    def get(self, profile_dir: Path) -> World:
        key_str = str(profile_dir)
        # Per-key lock to coalesce concurrent builds
        lock = self._build_locks.setdefault(key_str, threading.Lock())
        with lock:
            current_key = self._compute_key(profile_dir)
            cached = self._cache.get(key_str)
            if cached and cached[0] == current_key:
                return cached[1]
            world = self._build(profile_dir)
            self._cache[key_str] = (current_key, world)
            return world
```

---

## How fixers should consume this patch

For any Task in S1-S5:
1. Read `PLAN-PATCH.md` first; if your Task has a P-B* or P-F* entry, apply that patch's content as the source of truth.
2. Then read the corresponding plan file (`2026-06-14-mo2-mcp-S?-*.md`) for the rest of the Task structure (Steps, commits).
3. Test code in the plan still applies; only the impl code blocks may be replaced by PLAN-PATCH versions.
4. Commit message in plan still applies.

Patch coverage:
- **S1a Task 3** → P-B2 (system.shutdown handler ordering)
- **S1a Tasks 4-15** → P-F4 + P-F5 (ModState + separator detection)
- **S1b new Tasks 18.5a/b** → P-B5 (organizer.start_application/wait_for_application)
- **S1b new Task between 16-17** → P-F6 (profile.initialize)
- **S1b Task 18** → P-F3 (real virtual_file_tree impl)
- **S1b Tasks 23-24** → P-B7 (--game arg)
- **S1b Task 25** → P-B7 + P-F10 (game + lock)
- **S1b Task 26** → P-B7 (game propagation)
- **S1b new Tasks 28.5a/b/c** → P-B6 (archive.extract_all, install.conflict_preview, install.stage_fomod)
- **S2a Task S2.7** → P-B1 (PipeClient one-shot per call)
- **S2a new Task S2.4.5** → P-B4 (TS atomic.ts)
- **S2b Task S2.8** → P-B7 (--game arg pass-through)
- **S2b Task S2.13** → P-B3 (routeToPlanApply export)
- **S2b Task S2.14** → P-F9 (ToolContext extension)
- **S2b Task S2.15** → P-F8 (MCP protocol smoke test)
- **S4 Task S4.1** → P-F1 + P-F2 (extract path-helpers.ts + ini-helpers.ts)
- **S5a Task S5.3** → P-F7 (document in-place pipeClient swap)
