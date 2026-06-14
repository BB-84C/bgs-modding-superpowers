# S2a — MCP Server Skeleton + Config + Readers (Tasks S2.1-S2.7)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`.

**Goal:** Build the TypeScript `tools/mo2-mcp/` package skeleton: MCP SDK wiring, lifecycle state machine, config loader, `ModOrganizer.ini` parser, native profile reader, and broker named-pipe client. No tools registered yet (S3+).

**Architecture:** Port lifecycle pattern from `tools/xedit-mcp/src/index.ts:453-623`. Native TS profile reader avoids subprocess on the hot path. Pipe client connects to `mo2_agent_control` (S1) via Node `net.connect` on `\\.\pipe\<name>`.

**Tech Stack:** TypeScript 5+, Node 22+, `@modelcontextprotocol/sdk`, Zod schemas, vitest.

---

## File Structure
- Create: `tools/mo2-mcp/package.json`, `tsconfig.json`, `vitest.config.ts`
- Create: `tools/mo2-mcp/src/index.ts` (entry; bootstrap only in S2b)
- Create: `tools/mo2-mcp/src/lifecycle.ts` — state machine
- Create: `tools/mo2-mcp/src/config.ts` — `.mo2-mcp.json` loader
- Create: `tools/mo2-mcp/src/mo-ini.ts` — `ModOrganizer.ini` parser
- Create: `tools/mo2-mcp/src/profile-reader.ts` — modlist + plugins parser
- Create: `tools/mo2-mcp/src/detection.ts` — 7-signal MO2-running ladder
- Create: `tools/mo2-mcp/src/pipe-client.ts` — named-pipe broker client
- Create: `tools/mo2-mcp/src/types.ts` — shared `Mod` / `Plugin` / `Profile` types
- Tests under `tools/mo2-mcp/tests/`

---

## Task S2.1: Package skeleton

**Files:** `package.json`, `tsconfig.json`, `vitest.config.ts`, `src/index.ts` (stub)

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "mo2-mcp",
  "version": "0.1.0",
  "description": "Unified MO2 MCP server",
  "type": "module",
  "bin": { "mo2-mcp": "./dist/index.js" },
  "scripts": {
    "build": "tsc",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src tests"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.6.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^2.0.0",
    "@types/node": "^22.0.0"
  }
}
```

- [ ] **Step 2: tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "Node16", "moduleResolution": "Node16",
    "outDir": "dist", "rootDir": "src", "strict": true, "declaration": true,
    "resolveJsonModule": true, "esModuleInterop": true
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 3: stub `src/index.ts`**

```typescript
// Entry point; bootstrapped in S2b Task S2.14
console.error("mo2-mcp stub — bootstrap in S2.14");
process.exit(0);
```

- [ ] **Step 4: Verify build**

Run: `cd tools/mo2-mcp && npm install && npm run build`. Expect: `dist/index.js` created.

- [ ] **Step 5: Commit**

```bash
git add tools/mo2-mcp/
git commit -m "feat(mo2-mcp): TS package skeleton with MCP SDK + Zod + vitest"
```

---

## Task S2.2: Lifecycle state machine

Port from `tools/xedit-mcp/src/index.ts:453-623`. States: `not_started | starting | ready | failed`.

**Files:** `src/lifecycle.ts`, `tests/lifecycle.test.ts`

- [ ] **Step 1: Failing test**

```typescript
import { describe, it, expect } from "vitest";
import { Lifecycle } from "../src/lifecycle.js";

describe("Lifecycle", () => {
  it("starts in not_started", () => {
    const l = new Lifecycle();
    expect(l.state).toBe("not_started");
  });
  it("transitions not_started → starting → ready", () => {
    const l = new Lifecycle();
    l.markStarting();
    expect(l.state).toBe("starting");
    l.markReady({ sidecarPid: 1234 });
    expect(l.state).toBe("ready");
    expect(l.context.sidecarPid).toBe(1234);
  });
  it("rejects domain tools before ready", () => {
    const l = new Lifecycle();
    expect(l.requireReady()).toEqual({ ok: false, code: "not_ready", state: "not_started" });
  });
  it("requireReady returns ok when ready", () => {
    const l = new Lifecycle();
    l.markStarting();
    l.markReady({ sidecarPid: 1 });
    expect(l.requireReady()).toEqual({ ok: true });
  });
});
```

- [ ] **Step 2: Run, expect fail**

- [ ] **Step 3: Implement**

```typescript
// src/lifecycle.ts
export type LifecycleState = "not_started" | "starting" | "ready" | "failed";
export interface LifecycleContext {
  sidecarPid?: number;
  brokerPipeName?: string;
  failureReason?: string;
  startedAt?: number;
}
export class Lifecycle {
  state: LifecycleState = "not_started";
  context: LifecycleContext = {};
  markStarting(): void { this.state = "starting"; this.context.startedAt = Date.now(); }
  markReady(ctx: Partial<LifecycleContext>): void {
    this.state = "ready"; this.context = { ...this.context, ...ctx };
  }
  markFailed(reason: string): void { this.state = "failed"; this.context.failureReason = reason; }
  requireReady(): { ok: true } | { ok: false; code: "not_ready"; state: LifecycleState } {
    return this.state === "ready" ? { ok: true } : { ok: false, code: "not_ready", state: this.state };
  }
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
npm test -- lifecycle.test
git commit -am "feat(mo2-mcp): lifecycle state machine port from xedit-mcp"
```

---

## Task S2.3: Config loader (`.mo2-mcp.json` + env)

Spec: oracle traps §3.3 (latched at startup). Fields: `permission_ceiling`, `allowed_profiles`, `deny`, `snapshot_root`, `audit_root`.

**Files:** `src/config.ts`, `tests/config.test.ts`

- [ ] **Step 1: Failing test**

```typescript
import { loadConfig } from "../src/config.js";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

describe("loadConfig", () => {
  it("reads BGS_MO2_ROOT env and .mo2-mcp.json", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    await writeFile(join(root, ".mo2-mcp.json"), JSON.stringify({
      permission_ceiling: "metadata-editable",
      allowed_profiles: ["Default"]
    }));
    const cfg = await loadConfig({ mo2Root: root });
    expect(cfg.permissionCeiling).toBe("metadata-editable");
    expect(cfg.allowedProfiles).toEqual(["Default"]);
    expect(cfg.snapshotRoot).toBe(join(root, ".mo2-mcp", "snapshots"));
  });
  it("defaults to metadata-editable when config missing", async () => {
    const root = await mkdtemp(join(tmpdir(), "mo2-test-"));
    const cfg = await loadConfig({ mo2Root: root });
    expect(cfg.permissionCeiling).toBe("metadata-editable");
  });
  it("rejects missing BGS_MO2_ROOT", async () => {
    await expect(loadConfig({ mo2Root: undefined as any })).rejects.toThrow(/BGS_MO2_ROOT/);
  });
});
```

- [ ] **Step 2-3: Implement**

```typescript
// src/config.ts
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { z } from "zod";

export const ConfigSchema = z.object({
  permission_ceiling: z.enum(["read-only", "metadata-editable", "full-control"]).default("metadata-editable"),
  allowed_profiles: z.array(z.string()).default(["Default"]),
  deny: z.array(z.string()).default(["Stock Game/Data/**"]),
  snapshot_root: z.string().default(".mo2-mcp/snapshots"),
  audit_root: z.string().default(".mo2-mcp/audit"),
});

export interface Config {
  mo2Root: string;
  permissionCeiling: z.infer<typeof ConfigSchema>["permission_ceiling"];
  allowedProfiles: string[];
  deny: string[];
  snapshotRoot: string;
  auditRoot: string;
}

export async function loadConfig(opts: { mo2Root: string }): Promise<Config> {
  if (!opts.mo2Root) throw new Error("BGS_MO2_ROOT not set");
  let raw: unknown = {};
  try {
    raw = JSON.parse(await readFile(join(opts.mo2Root, ".mo2-mcp.json"), "utf8"));
  } catch { /* defaults */ }
  const parsed = ConfigSchema.parse(raw);
  return {
    mo2Root: opts.mo2Root,
    permissionCeiling: parsed.permission_ceiling,
    allowedProfiles: parsed.allowed_profiles,
    deny: parsed.deny,
    snapshotRoot: join(opts.mo2Root, parsed.snapshot_root),
    auditRoot: join(opts.mo2Root, parsed.audit_root),
  };
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): config loader (.mo2-mcp.json + BGS_MO2_ROOT)"
```

---

## Task S2.4: `ModOrganizer.ini` parser (TS port of S1b Task 19)

Spec: oracle traps §6.1. Qt INI array dialect. Preserve other sections verbatim for atomic rewrite later.

**Files:** `src/mo-ini.ts`, `tests/mo-ini.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/mo-ini.ts
import { readFile } from "node:fs/promises";

export interface MoIni {
  raw: string;
  general: { game?: string; gameName?: string; gamePath?: string; selectedProfile?: string };
  settings: { baseDirectory?: string; modDirectory?: string; downloadDirectory?: string; profilesDirectory?: string; overwriteDirectory?: string };
  customExecutables: Array<{ title: string; binary: string; arguments: string; workingDirectory: string; steamAppID?: string; ownicon?: boolean; hide?: boolean; }>;
  sectionRanges: Map<string, [number, number]>;  // for atomic rewrite preservation
}

export async function readMoIni(path: string): Promise<MoIni> {
  const raw = await readFile(path, "utf8");
  const lines = raw.split(/\r?\n/);
  const sectionRanges = new Map<string, [number, number]>();
  let currentSection = "";
  let sectionStart = 0;
  const sectionLines = new Map<string, string[]>();
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].trim().match(/^\[(.+)\]$/);
    if (m) {
      if (currentSection) sectionRanges.set(currentSection, [sectionStart, i - 1]);
      currentSection = m[1]; sectionStart = i; sectionLines.set(currentSection, []);
    } else if (currentSection) {
      sectionLines.get(currentSection)!.push(lines[i]);
    }
  }
  if (currentSection) sectionRanges.set(currentSection, [sectionStart, lines.length - 1]);

  const parseFlat = (s: string): Record<string, string> => {
    const o: Record<string, string> = {};
    for (const ln of sectionLines.get(s) ?? []) {
      const idx = ln.indexOf("=");
      if (idx > 0) o[ln.slice(0, idx).trim()] = ln.slice(idx + 1);
    }
    return o;
  };

  const general = parseFlat("General");
  const settings = parseFlat("Settings");

  // Qt array dialect for [customExecutables]
  const execs: any[] = [];
  const customLines = sectionLines.get("customExecutables") ?? [];
  const flat: Record<string, string> = {};
  for (const ln of customLines) {
    const idx = ln.indexOf("=");
    if (idx > 0) flat[ln.slice(0, idx).trim()] = ln.slice(idx + 1);
  }
  const size = parseInt(flat["size"] ?? "0", 10);
  const boolKeys = new Set(["ownicon", "hide", "toolbar", "minimizeToSystemTray"]);
  for (let i = 1; i <= size; i++) {
    const entry: any = {};
    for (const [k, v] of Object.entries(flat)) {
      const parts = k.split("\\");
      if (parts.length === 2 && parts[0] === String(i)) {
        entry[parts[1]] = boolKeys.has(parts[1]) ? v.toLowerCase() === "true" : v;
      }
    }
    if (entry.title) execs.push(entry);
  }

  return {
    raw,
    general: {
      game: general["game"], gameName: general["gameName"],
      gamePath: general["gamePath"], selectedProfile: general["selected_profile"],
    },
    settings: {
      baseDirectory: settings["base_directory"], modDirectory: settings["mod_directory"],
      downloadDirectory: settings["download_directory"],
      profilesDirectory: settings["profiles_directory"],
      overwriteDirectory: settings["overwrite_directory"],
    },
    customExecutables: execs,
    sectionRanges,
  };
}
```

Test verifies: parses sample INI with 2 executables, extracts settings + general, preserves section ranges.

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): ModOrganizer.ini parser with Qt array + section range preservation"
```

---

## Task S2.5: Native TS profile reader

Spec: oracle traps §1.2 — top of modlist.txt = highest priority. `*`-prefix in plugins.txt = enabled (NOT charrdge's inverted).

**Files:** `src/profile-reader.ts`, `tests/profile-reader.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/profile-reader.ts
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export interface ProfileMod { name: string; priority: number; enabled: boolean; isSeparator: boolean; }
export interface ProfilePlugin { name: string; enabled: boolean; isComment: boolean; }
export interface Profile {
  path: string; name: string;
  mods: ProfileMod[]; plugins: ProfilePlugin[];
  modlistMtimeMs: number; pluginsMtimeMs: number;
}

export async function readProfile(profileDir: string): Promise<Profile> {
  const modlistPath = join(profileDir, "modlist.txt");
  const pluginsPath = join(profileDir, "plugins.txt");
  const [modlistText, pluginsText] = await Promise.all([
    readFile(modlistPath, "utf8"),
    readFile(pluginsPath, "utf8").catch(() => ""),  // plugins.txt may not exist
  ]);
  const { statSync } = await import("node:fs");
  const mlStat = statSync(modlistPath);
  const plStat = pluginsPath ? statSync(pluginsPath) : { mtimeMs: 0 };

  // modlist.txt: top of file = highest priority. Per librarian-alpha confirmation.
  // But mobase IModList: index 0 = lowest priority. So we INVERT: top line gets highest numeric priority.
  const rawLines = modlistText.split(/\r?\n/).filter(l => l.length > 0 && !l.startsWith("#"));
  const modCount = rawLines.length;
  const mods: ProfileMod[] = rawLines.map((line, idx) => {
    const enabled = line.startsWith("+");
    const isSeparator = line.endsWith("_separator");
    const name = line.replace(/^[+\-*]/, "");
    return { name, enabled, isSeparator, priority: modCount - 1 - idx };
  });

  const plugins: ProfilePlugin[] = pluginsText.split(/\r?\n/)
    .filter(l => l.length > 0)
    .map(line => {
      const isComment = line.startsWith("#");
      const enabled = !isComment && line.startsWith("*");
      const name = line.replace(/^[#*]/, "").trim();
      return { name, enabled, isComment };
    });

  return {
    path: profileDir,
    name: profileDir.split(/[/\\]/).pop()!,
    mods, plugins,
    modlistMtimeMs: mlStat.mtimeMs,
    pluginsMtimeMs: plStat.mtimeMs,
  };
}
```

Test: write fixture profile with separators + enabled/disabled mods + plugins, verify priority assignment + `*` semantics.

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): TS profile reader (modlist.txt + plugins.txt with correct polarity)"
```

---

## Task S2.6: 7-signal MO2 detection ladder

Spec: oracle traps Open Q5. Three-tier ladder: process → shared memory → file lock.

**Files:** `src/detection.ts`, `tests/detection.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/detection.ts
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { access, constants } from "node:fs/promises";
const execFileP = promisify(execFile);

export interface DetectionResult {
  processRunning: boolean;
  sharedMemoryPresent: boolean;
  profileLockHeld: boolean;
  pid?: number;
  online: boolean;  // = all three true (high confidence)
}

export async function detectMo2Running(opts: { mo2Root: string; profileDir?: string }): Promise<DetectionResult> {
  // Tier 1: process list (cheapest)
  let pid: number | undefined;
  let processRunning = false;
  try {
    const { stdout } = await execFileP("tasklist", ["/FI", "IMAGENAME eq ModOrganizer.exe", "/FO", "CSV", "/NH"]);
    const match = stdout.match(/"ModOrganizer\.exe","(\d+)"/);
    if (match) { pid = parseInt(match[1], 10); processRunning = true; }
  } catch { /* assume not running */ }

  // Tier 2: shared memory probe via PowerShell
  let sharedMemoryPresent = false;
  if (processRunning) {
    try {
      const psScript = `
        Add-Type -AssemblyName System.Core
        for ($i = 1; $i -le 10; $i++) {
          $name = "mod_organizer_instance_$i"
          try {
            $mmf = [System.IO.MemoryMappedFiles.MemoryMappedFile]::OpenExisting($name)
            $mmf.Dispose()
            Write-Output $name
            break
          } catch {}
        }
      `;
      const { stdout } = await execFileP("pwsh", ["-NoProfile", "-Command", psScript]);
      sharedMemoryPresent = stdout.trim().startsWith("mod_organizer_instance_");
    } catch { /* assume not present */ }
  }

  // Tier 3: profile file exclusive lock
  let profileLockHeld = false;
  if (processRunning && opts.profileDir) {
    try {
      const { stdout } = await execFileP("pwsh", ["-NoProfile", "-Command", `
        try {
          $f = [System.IO.File]::Open('${opts.profileDir.replace(/\\/g, "\\\\")}/modlist.txt', 'Open', 'Read', 'None')
          $f.Close()
          Write-Output 'unlocked'
        } catch { Write-Output 'locked' }
      `]);
      profileLockHeld = stdout.trim() === "locked";
    } catch { /* unknown */ }
  }

  return {
    processRunning, sharedMemoryPresent, profileLockHeld, pid,
    online: processRunning && sharedMemoryPresent,
  };
}
```

Test: mock execFile, verify ladder runs in order, false-cases short-circuit.

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): 7-signal MO2-running detection ladder (process+shm+lock)"
```

---

## Task S2.7: Named-pipe broker client

Connect to `\\.\pipe\<name>` discovered from `endpoint.json`. Newline-delimited JSON per S1 broker protocol.

**Files:** `src/pipe-client.ts`, `tests/pipe-client.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/pipe-client.ts
import { connect, Socket } from "node:net";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export interface BrokerRequest { method: string; payload: Record<string, unknown>; }
export interface BrokerResponse { ok: boolean; result?: any; error?: { code: string; message: string }; }

export class PipeClient {
  private socket?: Socket;
  private buffer = "";
  private pending = new Map<string, (resp: BrokerResponse) => void>();
  private connected = false;

  async discoverAndConnect(mo2Root: string, timeoutMs = 5000): Promise<void> {
    const endpointPath = join(mo2Root, "plugins", "Mo2AgentControl", "bootstrap", "runtime", "endpoint.json");
    const info = JSON.parse(await readFile(endpointPath, "utf8"));
    const pipeName: string = info.endpoint;
    await this.connect(pipeName, timeoutMs);
  }

  private connect(pipeName: string, timeoutMs: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const path = `\\\\.\\pipe\\${pipeName.replace(/^\\\\\.\\pipe\\/, "")}`;
      const sock = connect(path);
      const timer = setTimeout(() => { sock.destroy(); reject(new Error("pipe connect timeout")); }, timeoutMs);
      sock.once("connect", () => {
        clearTimeout(timer); this.socket = sock; this.connected = true;
        sock.on("data", chunk => this.onData(chunk.toString("utf8")));
        sock.on("close", () => { this.connected = false; });
        resolve();
      });
      sock.once("error", err => { clearTimeout(timer); reject(err); });
    });
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, nl); this.buffer = this.buffer.slice(nl + 1);
      try {
        const resp = JSON.parse(line);
        const cb = this.pending.get(resp.request_id);
        if (cb) { this.pending.delete(resp.request_id); cb(resp); }
      } catch { /* swallow malformed */ }
    }
  }

  async call(method: string, payload: Record<string, unknown>, timeoutMs = 30000): Promise<BrokerResponse> {
    if (!this.connected || !this.socket) throw new Error("pipe not connected");
    const id = `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const req = { protocol_version: "1", request_id: id, session_id: "mo2-mcp", method, payload };
    return new Promise<BrokerResponse>((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error("pipe call timeout")); }, timeoutMs);
      this.pending.set(id, resp => { clearTimeout(timer); resolve(resp); });
      this.socket!.write(JSON.stringify(req) + "\n");
    });
  }

  isConnected(): boolean { return this.connected; }
  close(): void { this.socket?.end(); this.connected = false; }
}
```

Test: spawn mock pipe server, verify request/response round-trip + timeout behavior.

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): named-pipe broker client with endpoint discovery"
```

---

## End of S2a

7 tasks land: TS package skeleton, lifecycle, config loader, MO ini parser, profile reader, detection ladder, pipe client. ~7 commits.

Continue in `2026-06-14-mo2-mcp-S2b-mcp-pipeline-and-bootstrap.md`:
- S2.8 Python sidecar spawner + JSON-RPC client
- S2.9 Rule engine port
- S2.10 JSONL audit logger
- S2.11 Snapshot manager
- S2.12 Lease verifier (content hash + structural fingerprint)
- S2.13 Plan/apply pipeline
- S2.14 MCP server bootstrap + empty tool registry
- S2.15 End-to-end smoke (server starts, `mo2_status` returns)
