# S2b — Sidecar Spawner + Pipeline + Bootstrap (Tasks S2.8-S2.15)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Continues from S2a.

**Goal:** Finish the MCP server framework: spawn the Python sidecar (S1 substrate), port the rule engine pipeline from `xedit-mcp`, implement audit + snapshot + lease verifier, wire plan/apply pipeline, bootstrap the MCP server with empty tool registry, and smoke test end-to-end.

**Architecture:** `xedit-mcp/src/pipeline/{rules,forward,state-precheck}.ts` ports nearly verbatim — only the registry's rule set changes. Plan/apply pipeline is one MCP tool with `mode: "plan" | "apply"` (oracle traps §3.1). Sidecar spawn matches S1b Task 23 entry point. Bootstrap wires Lifecycle → Config → Detection → Sidecar → PipeClient → ToolRegistry → MCP server.

**Tech Stack:** Same as S2a + `child_process.spawn`, JSON-RPC over stdio to sidecar.

---

## File Structure
- Create: `src/sidecar-client.ts` — Python sidecar spawn + JSON-RPC
- Create: `src/pipeline/rules.ts`, `pipeline/registry.ts`, `pipeline/state-precheck.ts`, `pipeline/forward.ts`, `pipeline/compose.ts`
- Create: `src/audit.ts` — JSONL logger
- Create: `src/snapshot.ts` — snapshot-before-write manager
- Create: `src/lease.ts` — content hash + structural fingerprint
- Create: `src/plan-apply.ts` — pipeline orchestration
- Create: `src/tool-registry.ts` — registry + plan/apply tool template
- Modify: `src/index.ts` — bootstrap
- Create: `src/types.ts` — shared types (Plan, Lease, ToolContext, AuditRecord)

---

## Task S2.8: Python sidecar spawner + JSON-RPC client

Spec: oracle traps §1.4 — await `{"ready": true}` on stdout before declaring ready.

**Files:** `src/sidecar-client.ts`, `tests/sidecar-client.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/sidecar-client.ts
import { spawn, ChildProcessWithoutNullStreams } from "node:child_process";

export interface SidecarOpts { pythonPath?: string; modsRoot: string; profileDir: string; }

export class SidecarClient {
  private proc?: ChildProcessWithoutNullStreams;
  private buffer = "";
  private pending = new Map<string | number, (resp: any) => void>();
  private nextId = 1;
  private ready = false;
  private readyPromise?: Promise<void>;

  async start(opts: SidecarOpts): Promise<void> {
    const python = opts.pythonPath ?? "python";
    this.proc = spawn(python, ["-m", "mo2_mcp_sidecar",
      "--mods-root", opts.modsRoot, "--profile-dir", opts.profileDir],
      { stdio: ["pipe", "pipe", "pipe"] });

    this.proc.stdout.on("data", c => this.onData(c.toString("utf8")));
    this.proc.stderr.on("data", c => process.stderr.write(`[sidecar] ${c}`));
    this.proc.on("exit", code => { this.ready = false; });

    this.readyPromise = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("sidecar startup timeout 30s")), 30000);
      const checkReady = () => {
        if (this.ready) { clearTimeout(timer); resolve(); }
        else setTimeout(checkReady, 50);
      };
      checkReady();
    });
    return this.readyPromise;
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, nl); this.buffer = this.buffer.slice(nl + 1);
      let msg: any;
      try { msg = JSON.parse(line); } catch { continue; }
      if (msg.ready === true) { this.ready = true; continue; }
      const cb = this.pending.get(msg.id);
      if (cb) { this.pending.delete(msg.id); cb(msg); }
    }
  }

  async call(method: string, params: any = {}, timeoutMs = 60000): Promise<any> {
    if (!this.ready || !this.proc) throw new Error("sidecar_not_ready");
    const id = this.nextId++;
    const req = { jsonrpc: "2.0", id, method, params };
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error("sidecar call timeout")); }, timeoutMs);
      this.pending.set(id, msg => {
        clearTimeout(timer);
        if (msg.error) reject(new Error(`sidecar error ${msg.error.code}: ${msg.error.message}`));
        else resolve(msg.result);
      });
      this.proc!.stdin.write(JSON.stringify(req) + "\n");
    });
  }

  isReady(): boolean { return this.ready; }
  async stop(): Promise<void> { this.proc?.kill(); }
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): sidecar JSON-RPC client with ready-signal wait"
```

---

## Task S2.9: Rule engine port

Port `tools/xedit-mcp/src/pipeline/{rules,registry}.ts` adapting to MO2 rule signatures. CRITICAL/HIGH/MEDIUM severities.

**Files:** `src/pipeline/rules.ts`, `pipeline/registry.ts`, `src/types.ts`, `tests/pipeline.test.ts`

- [ ] **Step 1-3: Implement**

```typescript
// src/types.ts (extend)
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM";
export type RuleDecision = "pass" | "warn" | "block";
export interface RuleFinding { code: string; severity: Severity; decision: RuleDecision; message: string; data?: any; }
export interface ToolContext { config: import("./config.js").Config; pipeClient?: import("./pipe-client.js").PipeClient; sidecar?: import("./sidecar-client.js").SidecarClient; sessionId: string; }
export interface Rule { id: string; severity: Severity; appliesTo: (toolName: string) => boolean; evaluate: (ctx: ToolContext, args: any) => Promise<RuleFinding | null>; }
```

```typescript
// src/pipeline/rules.ts
import type { Rule, RuleFinding, ToolContext } from "../types.js";

export async function runRules(rules: Rule[], toolName: string, ctx: ToolContext, args: any): Promise<RuleFinding[]> {
  const out: RuleFinding[] = [];
  for (const rule of rules.filter(r => r.appliesTo(toolName))) {
    try { const f = await rule.evaluate(ctx, args); if (f) out.push(f); }
    catch (e) { out.push({ code: `${rule.id}-error`, severity: "MEDIUM", decision: "warn", message: String(e) }); }
  }
  return out;
}

export function hasBlocking(findings: RuleFinding[]): boolean { return findings.some(f => f.decision === "block"); }
```

```typescript
// src/pipeline/registry.ts
import type { Rule } from "../types.js";

const rules: Rule[] = [];
export function registerRule(r: Rule): void { rules.push(r); }
export function getAllRules(): Rule[] { return [...rules]; }

// S2 ships with empty registry; rules added per-tool in S3-S5
```

Initial rules (ship in S2):

```typescript
// src/pipeline/rules/STOCK001-stock-game-deny.ts
import { registerRule } from "../registry.js";
registerRule({
  id: "STOCK001",
  severity: "CRITICAL",
  appliesTo: () => true,  // applies to ALL tools
  evaluate: async (ctx, args) => {
    const denyPattern = /Stock Game[/\\]Data[/\\]/i;
    const checkPath = (p: string) => denyPattern.test(p);
    const paths = [args?.path, args?.virtual_path, args?.archive_path].filter(Boolean);
    for (const p of paths) {
      if (typeof p === "string" && checkPath(p)) {
        return { code: "STOCK001", severity: "CRITICAL", decision: "block",
                 message: `Stock Game/Data path mutation forbidden: ${p}` };
      }
    }
    return null;
  },
});
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): rule engine ported from xedit-mcp + STOCK001 hard-deny"
```

---

## Task S2.10: JSONL audit logger

Spec: oracle traps §8.1 — single writer (MCP), session+date keyed filename, never-throws.

**Files:** `src/audit.ts`, `tests/audit.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/audit.ts
import { appendFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

export type AuditDecision = "ok" | "refused" | "plan_generated" | "applied" | "lease_violation" | "rolled_back";

export interface AuditRecord {
  ts: string;
  sessionId: string;
  tool: string;
  mode?: "plan" | "apply";
  argsHash: string;
  decision: AuditDecision;
  ruleFindings?: any[];
  planId?: string;
  snapshotId?: string;
  durationMs: number;
  error?: { code: string; message: string };
}

export class AuditLogger {
  constructor(private auditRoot: string, private sessionId: string) {}

  private filePath(): string {
    const date = new Date().toISOString().slice(0, 10);
    return join(this.auditRoot, `${this.sessionId}-${date}.jsonl`);
  }

  async log(record: AuditRecord): Promise<void> {
    try {
      await mkdir(this.auditRoot, { recursive: true });
      await appendFile(this.filePath(), JSON.stringify(record) + "\n", "utf8");
    } catch (e) {
      // Never throw from logger
      process.stderr.write(`[audit] log failed: ${e}\n`);
    }
  }
}

import { createHash } from "node:crypto";
export function hashArgs(args: any): string {
  return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): JSONL audit logger (per-session, per-day, never-throws)"
```

---

## Task S2.11: Snapshot manager

Spec: oracle traps §3.4 — `<MO2_Root>/.mo2-mcp/snapshots/<session_id>/<timestamp>-<tool>/`.

**Files:** `src/snapshot.ts`, `tests/snapshot.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/snapshot.ts
import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

export interface SnapshotRecord {
  snapshotId: string; tool: string; ts: string;
  files: { source: string; backup: string }[];
}

export class SnapshotManager {
  constructor(private snapshotRoot: string, private sessionId: string) {}

  async snapshot(tool: string, sourceFiles: string[]): Promise<SnapshotRecord> {
    const snapshotId = randomUUID();
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const dir = join(this.snapshotRoot, this.sessionId, `${ts}-${tool}`);
    await mkdir(dir, { recursive: true });
    const files: { source: string; backup: string }[] = [];
    for (const src of sourceFiles) {
      const rel = src.replace(/[/\\]/g, "_").replace(/[<>:"|?*]/g, "");
      const backup = join(dir, rel);
      try { await cp(src, backup, { recursive: true }); files.push({ source: src, backup }); }
      catch { /* file may not exist yet — record as missing */ }
    }
    const record: SnapshotRecord = { snapshotId, tool, ts, files };
    await writeFile(join(dir, "manifest.json"), JSON.stringify(record, null, 2));
    return record;
  }

  async restore(snapshotId: string): Promise<{ restored: string[]; failed: string[] }> {
    // Find snapshot dir by snapshotId scan
    const { readdir } = await import("node:fs/promises");
    const sessionDir = join(this.snapshotRoot, this.sessionId);
    const dirs = await readdir(sessionDir);
    for (const d of dirs) {
      const manifestPath = join(sessionDir, d, "manifest.json");
      try {
        const m: SnapshotRecord = JSON.parse(await readFile(manifestPath, "utf8"));
        if (m.snapshotId === snapshotId) {
          const restored: string[] = []; const failed: string[] = [];
          for (const { source, backup } of m.files) {
            try { await cp(backup, source, { recursive: true, force: true }); restored.push(source); }
            catch { failed.push(source); }
          }
          return { restored, failed };
        }
      } catch { /* skip malformed */ }
    }
    throw new Error(`snapshot_not_found: ${snapshotId}`);
  }
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): snapshot manager with restore by snapshotId"
```

---

## Task S2.12: Lease verifier

Spec: oracle traps §3.2. Content hash for text, structural fingerprint for dirs. **No mtime.**

**Files:** `src/lease.ts`, `tests/lease.test.ts`

- [ ] **Step 1-3: Test + impl**

```typescript
// src/lease.ts
import { readFile, stat, readdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";

export interface LeaseComponent {
  path: string;
  kind: "text-file" | "directory";
  contentHash?: string;
  fileCount?: number;
  totalSize?: number;
  size?: number;
}

export interface Lease { token: string; components: LeaseComponent[]; }

export async function fingerprintFile(path: string): Promise<LeaseComponent> {
  try {
    const content = await readFile(path);
    const contentHash = createHash("sha256").update(content).digest("hex");
    return { path, kind: "text-file", contentHash, size: content.length };
  } catch (e: any) {
    if (e.code === "ENOENT") return { path, kind: "text-file", contentHash: "missing", size: 0 };
    throw e;
  }
}

export async function fingerprintDir(path: string): Promise<LeaseComponent> {
  let fileCount = 0; let totalSize = 0;
  async function walk(d: string): Promise<void> {
    const entries = await readdir(d, { withFileTypes: true });
    for (const e of entries) {
      const full = join(d, e.name);
      if (e.isDirectory()) await walk(full);
      else { fileCount++; const s = await stat(full); totalSize += s.size; }
    }
  }
  try { await walk(path); }
  catch (e: any) { if (e.code === "ENOENT") return { path, kind: "directory", fileCount: 0, totalSize: 0 }; throw e; }
  return { path, kind: "directory", fileCount, totalSize };
}

export async function computeLease(targets: Array<{ path: string; kind: "text-file" | "directory" }>): Promise<Lease> {
  const components = await Promise.all(targets.map(t =>
    t.kind === "text-file" ? fingerprintFile(t.path) : fingerprintDir(t.path)
  ));
  const token = createHash("sha256").update(JSON.stringify(components)).digest("hex");
  return { token, components };
}

export interface LeaseDrift {
  path: string;
  planComponent: LeaseComponent;
  currentComponent: LeaseComponent;
}

export async function verifyLease(lease: Lease): Promise<{ valid: true } | { valid: false; drift: LeaseDrift[] }> {
  const drift: LeaseDrift[] = [];
  for (const planComp of lease.components) {
    const current = planComp.kind === "text-file"
      ? await fingerprintFile(planComp.path)
      : await fingerprintDir(planComp.path);
    if (JSON.stringify(current) !== JSON.stringify(planComp)) {
      drift.push({ path: planComp.path, planComponent: planComp, currentComponent: current });
    }
  }
  return drift.length === 0 ? { valid: true } : { valid: false, drift };
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): lease verifier (content hash + structural fingerprint)"
```

---

## Task S2.13: Plan/apply pipeline

Spec: oracle traps §3.1. One tool per behavior with `mode: "plan" | "apply"`.

**Files:** `src/plan-apply.ts`, `tests/plan-apply.test.ts`

- [ ] **Step 1-3: Implement**

```typescript
// src/plan-apply.ts
import { randomUUID } from "node:crypto";
import { Lease, computeLease, verifyLease } from "./lease.js";
import { SnapshotManager } from "./snapshot.js";

export interface PlanRecord {
  planId: string;
  tool: string;
  args: any;
  diff: string;
  affectedFiles: string[];
  lease: Lease;
  snapshotId?: string;
  expiresAt: number;  // ms timestamp
}

export class PlanCache {
  private plans = new Map<string, PlanRecord>();
  private defaultTtlMs = 15 * 60 * 1000;  // 15 min

  store(plan: Omit<PlanRecord, "planId" | "expiresAt"> & { ttlMs?: number }): PlanRecord {
    const planId = randomUUID();
    const expiresAt = Date.now() + (plan.ttlMs ?? this.defaultTtlMs);
    const rec: PlanRecord = { planId, expiresAt, ...plan };
    this.plans.set(planId, rec);
    return rec;
  }

  get(planId: string): PlanRecord | null {
    const rec = this.plans.get(planId);
    if (!rec) return null;
    if (Date.now() > rec.expiresAt) { this.plans.delete(planId); return null; }
    return rec;
  }

  consume(planId: string): PlanRecord | null {
    const rec = this.get(planId);
    if (rec) this.plans.delete(planId);
    return rec;
  }

  purgeExpired(): void {
    const now = Date.now();
    for (const [id, rec] of this.plans) if (now > rec.expiresAt) this.plans.delete(id);
  }
}

export interface PlanApplyHandler {
  toolName: string;
  buildPlan(args: any, ctx: import("./types.js").ToolContext): Promise<{ diff: string; affectedFiles: string[]; targets: Array<{ path: string; kind: "text-file" | "directory" }> }>;
  applyMutation(plan: PlanRecord, ctx: import("./types.js").ToolContext): Promise<any>;
}

export async function runPlanMode(
  handler: PlanApplyHandler, args: any, ctx: import("./types.js").ToolContext,
  cache: PlanCache, snapshots: SnapshotManager
): Promise<{ ok: true; result: { mode: "plan"; planId: string; lease_token: string; diff: string; affected_files: string[]; expires_at: string } }> {
  const built = await handler.buildPlan(args, ctx);
  const lease = await computeLease(built.targets);
  const snapshot = await snapshots.snapshot(handler.toolName, built.affectedFiles);
  const rec = cache.store({
    tool: handler.toolName, args, diff: built.diff,
    affectedFiles: built.affectedFiles, lease, snapshotId: snapshot.snapshotId,
  });
  return { ok: true, result: { mode: "plan", planId: rec.planId, lease_token: lease.token,
    diff: built.diff, affected_files: built.affectedFiles,
    expires_at: new Date(rec.expiresAt).toISOString() } };
}

export async function runApplyMode(
  handler: PlanApplyHandler, args: { plan_id: string; lease_token: string },
  ctx: import("./types.js").ToolContext, cache: PlanCache
): Promise<{ ok: boolean; result?: any; error?: any }> {
  const rec = cache.consume(args.plan_id);
  if (!rec) return { ok: false, error: { code: "plan_expired_or_unknown", message: `plan ${args.plan_id} not found or expired` } };
  if (rec.lease.token !== args.lease_token) return { ok: false, error: { code: "lease_token_mismatch", message: "stored plan lease differs from supplied" } };

  const v = await verifyLease(rec.lease);
  if (!v.valid) return { ok: false, error: { code: "lease_violation",
    message: "Profile state changed since plan was generated",
    drift: v.drift, hint: "Re-run the plan to get updated state." } };

  const result = await handler.applyMutation(rec, ctx);
  return { ok: true, result: { mode: "apply", plan_id: rec.planId, snapshot_id: rec.snapshotId, ...result } };
}
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): plan/apply pipeline with PlanCache + lease verification"
```

---

## Task S2.14: MCP server bootstrap (empty tool registry)

Wire everything: lifecycle → config → detection → sidecar spawn → pipe connect → MCP server start. Register zero tools (S3+ adds them).

**Files:** `src/index.ts` (replace stub from S2.1), `src/tool-registry.ts`

- [ ] **Step 1-3: Implement**

```typescript
// src/tool-registry.ts
import { z } from "zod";
import type { ToolContext } from "./types.js";

export interface ToolDef {
  name: string;
  description: string;
  inputSchema: z.ZodTypeAny;
  handler: (args: any, ctx: ToolContext) => Promise<any>;
  tier: "T1" | "T2" | "T3";
}

const registry = new Map<string, ToolDef>();
export function registerTool(def: ToolDef): void { registry.set(def.name, def); }
export function getTool(name: string): ToolDef | undefined { return registry.get(name); }
export function getAllTools(): ToolDef[] { return [...registry.values()]; }
```

```typescript
// src/index.ts (full bootstrap)
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { randomUUID } from "node:crypto";
import { Lifecycle } from "./lifecycle.js";
import { loadConfig } from "./config.js";
import { readMoIni } from "./mo-ini.js";
import { detectMo2Running } from "./detection.js";
import { PipeClient } from "./pipe-client.js";
import { SidecarClient } from "./sidecar-client.js";
import { AuditLogger, hashArgs } from "./audit.js";
import { SnapshotManager } from "./snapshot.js";
import { PlanCache } from "./plan-apply.js";
import { getAllTools, getTool } from "./tool-registry.js";
import { runRules, hasBlocking } from "./pipeline/rules.js";
import { getAllRules } from "./pipeline/registry.js";
import "./pipeline/rules/STOCK001-stock-game-deny.js";  // side-effect registration
import { join } from "node:path";

async function main(): Promise<void> {
  const sessionId = randomUUID();
  const lifecycle = new Lifecycle();
  lifecycle.markStarting();

  const mo2Root = process.env.BGS_MO2_ROOT;
  if (!mo2Root) { console.error("BGS_MO2_ROOT not set"); process.exit(1); }
  const config = await loadConfig({ mo2Root });

  // Test-write probe for read-only mode (charrdge :ro defense-in-depth)
  if (config.permissionCeiling === "read-only") {
    const { writeFile, unlink } = await import("node:fs/promises");
    const probe = join(mo2Root, ".mo2-mcp", "probe");
    try {
      await writeFile(probe, "probe");
      await unlink(probe);
      console.error("read-only ceiling but write succeeded; refusing to start");
      process.exit(2);
    } catch { /* expected: write failed → OK */ }
  }

  const ini = await readMoIni(join(mo2Root, "ModOrganizer.ini"));
  const profileDir = join(mo2Root, "profiles", config.allowedProfiles[0]);

  const sidecar = new SidecarClient();
  try { await sidecar.start({ modsRoot: ini.settings.modDirectory ?? join(mo2Root, "mods"), profileDir }); }
  catch (e) { console.error(`sidecar failed: ${e}`); /* asset tools will return sidecar_not_ready */ }

  const detection = await detectMo2Running({ mo2Root, profileDir });
  const pipe = new PipeClient();
  if (detection.online) { try { await pipe.discoverAndConnect(mo2Root); } catch { /* offline mode */ } }

  const audit = new AuditLogger(config.auditRoot, sessionId);
  const snapshots = new SnapshotManager(config.snapshotRoot, sessionId);
  const plans = new PlanCache();
  const rules = getAllRules();

  const ctx = { config, pipeClient: pipe.isConnected() ? pipe : undefined,
                sidecar: sidecar.isReady() ? sidecar : undefined, sessionId };

  const server = new Server({ name: "mo2-mcp", version: "0.1.0" }, { capabilities: { tools: {} } });

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: getAllTools().map(t => ({ name: t.name, description: t.description, inputSchema: t.inputSchema })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async req => {
    const t0 = Date.now();
    const tool = getTool(req.params.name);
    if (!tool) {
      await audit.log({ ts: new Date().toISOString(), sessionId, tool: req.params.name,
        argsHash: hashArgs(req.params.arguments), decision: "refused",
        durationMs: Date.now() - t0, error: { code: "tool_not_found", message: req.params.name } });
      return { content: [{ type: "text", text: JSON.stringify({ ok: false, error: { code: "tool_not_found" } }) }] };
    }
    const findings = await runRules(rules, tool.name, ctx, req.params.arguments);
    if (hasBlocking(findings)) {
      const blocking = findings.find(f => f.decision === "block")!;
      await audit.log({ ts: new Date().toISOString(), sessionId, tool: tool.name,
        argsHash: hashArgs(req.params.arguments), decision: "refused", ruleFindings: findings,
        durationMs: Date.now() - t0, error: { code: blocking.code, message: blocking.message } });
      return { content: [{ type: "text", text: JSON.stringify({ ok: false, error: blocking }) }] };
    }
    try {
      const result = await tool.handler(req.params.arguments, ctx);
      await audit.log({ ts: new Date().toISOString(), sessionId, tool: tool.name,
        mode: req.params.arguments?.mode, argsHash: hashArgs(req.params.arguments),
        decision: result.ok === false ? "refused" : (req.params.arguments?.mode === "plan" ? "plan_generated" :
          req.params.arguments?.mode === "apply" ? "applied" : "ok"),
        durationMs: Date.now() - t0, planId: result.result?.planId, snapshotId: result.result?.snapshot_id });
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    } catch (e: any) {
      await audit.log({ ts: new Date().toISOString(), sessionId, tool: tool.name,
        argsHash: hashArgs(req.params.arguments), decision: "refused",
        durationMs: Date.now() - t0, error: { code: "internal_error", message: e.message } });
      return { content: [{ type: "text", text: JSON.stringify({ ok: false, error: { code: "internal_error", message: e.message } }) }] };
    }
  });

  lifecycle.markReady({ sidecarPid: undefined, brokerPipeName: pipe.isConnected() ? "connected" : undefined });
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write(`mo2-mcp ready (session ${sessionId})\n`);
}

main().catch(e => { console.error(e); process.exit(1); });
```

- [ ] **Step 4-5: Verify + commit**

```bash
git commit -am "feat(mo2-mcp): bootstrap with lifecycle+config+detection+pipe+sidecar+audit"
```

---

## Task S2.15: End-to-end smoke

Run server in test mode, verify `tools/list` returns empty, lifecycle reports ready, server exits cleanly on stdin close.

**Files:** `tests/smoke.test.ts`, gated subset under `tests/smoke-mo2.test.ts`

- [ ] **Step 1-3: Test**

```typescript
import { spawn } from "node:child_process";
import { describe, it, expect } from "vitest";

describe("smoke", () => {
  it("server starts and lists empty tools when no tools registered", async () => {
    const env = { ...process.env, BGS_MO2_ROOT: "/tmp/mo2-test" };
    // Setup minimal mo2 root
    const { mkdir, writeFile } = await import("node:fs/promises");
    await mkdir("/tmp/mo2-test/profiles/Default", { recursive: true });
    await writeFile("/tmp/mo2-test/profiles/Default/modlist.txt", "");
    await writeFile("/tmp/mo2-test/ModOrganizer.ini", "[General]\ngame=fallout4\n[Settings]\nbase_directory=/tmp/mo2-test\n");

    const proc = spawn("node", ["./dist/index.js"], { stdio: ["pipe", "pipe", "pipe"], env });
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }) + "\n");
    const resp = await new Promise<string>(resolve => {
      proc.stdout.once("data", c => resolve(c.toString("utf8")));
    });
    proc.kill();
    const parsed = JSON.parse(resp.split("\n")[0]);
    expect(parsed.result.tools).toEqual([]);
  });
});
```

- [ ] **Step 4-5: Verify + commit + close S2**

```bash
npm test
git commit -am "test(mo2-mcp): smoke (server starts, empty tool list, clean shutdown)"
```

---

## End of S2

After S2a + S2b (15 tasks):

**Substrate landed:**
- `tools/mo2-mcp/` complete TS package: lifecycle, config, MO ini parser, profile reader, detection ladder, pipe client, sidecar client, rule engine, audit, snapshot, lease, plan/apply pipeline, MCP bootstrap, empty tool registry
- STOCK001 hard-deny rule active

**Verification:** All vitest unit tests pass. Smoke test confirms server boots + tools/list works. ~15 commits.

**Review gate:** Run `requesting-code-review` against S2 substrate. Specifically verify:
- Lease never uses mtime
- Audit never throws
- Plan/apply correctly clears expired plans
- Bootstrap correctly handles offline mode (no MO2, no sidecar)

Then start S3 (T1 read tools).
