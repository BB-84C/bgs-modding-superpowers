# xEdit Skills + Harness MCP — Batch 1 (Vertical Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the xEdit harness-MCP and the hub-and-spoke skills layer end-to-end for the **conflict-audit** workflow (W2), proving the 7-stage pipeline pattern against the live MO2-backed daemon so that batches 2–4 can replicate the template.

**Architecture:** A TypeScript MCP server (`tools/xedit-mcp/`) wraps the existing `xedit-client.ps1` outer client. Every tool call traverses a fixed pipeline (schema → state → rules → forward → envelope → audit). Batch 1 ships pipeline stages [1][2][3][6][7]; snapshot [4] and preview [5] land in Batch 3. Skills (`xedit-automation` hub + `xedit-knowledgebase` + `xedit-conflict-audit`) teach the agent the toolbox, routing, anti-patterns, and the W2 workflow.

**Tech Stack:** TypeScript 5.x, Node 22, npm 10, `@modelcontextprotocol/sdk`, `vitest` for tests, `zod` for schema validation. Existing PowerShell `xedit-client.ps1` is invoked via `child_process` — not rewritten.

**Spec:** `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`

**Scope of this plan:** Batch 1 only — vertical slice for conflict audit (W2). Batches 2–4 will get their own plans after Batch 1 dogfooding informs them. Do NOT pull in Batch 2+ tools, rules, or skills in this plan.

---

## File Structure

```
tools/xedit-mcp/                                  (new package)
  package.json
  tsconfig.json
  vitest.config.ts
  README.md
  src/
    index.ts                      MCP server entry, registers tools
    types.ts                      Envelope, Rule, Finding, ToolContext, error codes
    audit.ts                      Append-only JSONL audit logger
    envelope.ts                   Standard response envelope shaper
    daemon-adapter.ts             Spawns xedit-client.ps1 process launch/wait/automation call
    session.ts                    Daemon lifecycle: ensure-ready, describe, dirty-state
    capabilities-digest.ts        Curated 47-command digest (Batch 1 source of truth)
    pipeline/
      validate.ts                 Stage [1] — zod-based arg validator
      state-precheck.ts           Stage [2] — daemon/load-order/consent gates
      rules.ts                    Stage [3] — registry runner
      forward.ts                  Stage [6] — invoke daemon-adapter, wrap errors
      compose.ts                  Wires [1] → [2] → [3] → [6] → [7]
    rules/
      registry.ts                 Loads rules from rules/*.ts, indexes by appliesTo
      LOAD001.ts                  Only fully-implemented rule for Batch 1
    tools/
      session.ts                  xedit_session
      list-capabilities.ts        xedit_list_capabilities
      find-record.ts              xedit_find_record
      read-record.ts              xedit_read_record
      inspect-conflicts.ts        xedit_inspect_conflicts
      call.ts                     xedit_call (atomic passthrough)
  tests/
    unit/
      envelope.test.ts
      audit.test.ts
      validate.test.ts
      state-precheck.test.ts
      rules.test.ts
      LOAD001.test.ts
      list-capabilities.test.ts
      find-record.test.ts
      read-record.test.ts
      inspect-conflicts.test.ts
      call.test.ts
    integration/
      live-conflict-audit.test.ts  Against .artifacts/mo2/ live daemon
    fixtures/
      daemon-mock.ts               In-memory daemon responder for unit tests

.opencode/skills/xedit-automation/                (new)
  SKILL.md
  xedit-knowledgebase.md

.opencode/skills/xedit-conflict-audit/            (new)
  SKILL.md

.opencode/artifacts/xedit-mcp/                    (runtime; .gitignored)
  audit/YYYY-MM-DD.jsonl
  acceptance/batch1/...
```

`.gitignore`: ensure `.opencode/artifacts/xedit-mcp/` (and existing `.opencode/artifacts/` if not already ignored) is covered.

---

## Phase A — Project Scaffolding & Core Types

### Task 1: Initialize the `tools/xedit-mcp/` package

**Files:**
- Create: `tools/xedit-mcp/package.json`
- Create: `tools/xedit-mcp/tsconfig.json`
- Create: `tools/xedit-mcp/vitest.config.ts`
- Create: `tools/xedit-mcp/README.md`
- Create: `tools/xedit-mcp/.gitignore`
- Modify: `.gitignore` (repo root) — ensure `.opencode/artifacts/xedit-mcp/` is ignored

**Rationale:** Independent TypeScript package per spec §16 placement. Vitest chosen for speed and zero-config TS support. Stay decoupled from `.opencode/package.json` (which pins the OpenCode plugin SDK only).

- [ ] **Step 1: Create `tools/xedit-mcp/package.json`**

```json
{
  "name": "xedit-mcp",
  "version": "0.1.0",
  "description": "Harness MCP server for the forked xEdit automation daemon.",
  "type": "module",
  "private": true,
  "bin": {
    "xedit-mcp": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "start": "node dist/index.js",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:integration": "vitest run tests/integration",
    "typecheck": "tsc -p tsconfig.json --noEmit"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  },
  "engines": {
    "node": ">=22"
  }
}
```

- [ ] **Step 2: Create `tools/xedit-mcp/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": false,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

- [ ] **Step 3: Create `tools/xedit-mcp/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
    testTimeout: 10_000,
  },
});
```

- [ ] **Step 4: Create `tools/xedit-mcp/.gitignore`**

```
node_modules/
dist/
*.log
.vitest-cache/
```

- [ ] **Step 5: Create `tools/xedit-mcp/README.md`**

```markdown
# xedit-mcp

Harness MCP server for the forked xEdit automation daemon. See the design spec at
`docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`.

## Quick start

```bash
npm install
npm run build
npm test
```

## Architecture

Every MCP tool call traverses a fixed 7-stage pipeline:

1. Schema/argument validation
2. State precheck (daemon, load-order, consent)
3. Rule registry scan
4. Snapshot before mutate (Batch 3+)
5. Preview / consent gate (Batch 3+)
6. Forward to daemon via `tools/mo2-vfs-launcher/xedit-client.ps1`
7. Envelope shape + audit log

Batch 1 ships stages [1][2][3][6][7] and the read-only tools needed for the
conflict-audit (W2) workflow.
```

- [ ] **Step 6: Ensure `.opencode/artifacts/xedit-mcp/` is gitignored**

Inspect the root `.gitignore`:

```bash
grep -n "opencode/artifacts" .gitignore
```

If `.opencode/artifacts/` (or a parent that covers it) is not present, append:

```
.opencode/artifacts/xedit-mcp/
```

- [ ] **Step 7: Install dependencies and verify scaffold builds**

```bash
cd tools/xedit-mcp
npm install
npm run typecheck
npm test
```

Expected: `typecheck` passes with no errors (no source yet, so empty src is fine — create `src/index.ts` with a single `export {};` first if `tsc` complains). `npm test` passes with "no test files found" (acceptable).

If `src/index.ts` is needed for `tsc` to be happy:

```ts
// src/index.ts
export {};
```

- [ ] **Step 8: Commit**

```bash
git add tools/xedit-mcp/ .gitignore
git commit -m "feat(xedit-mcp): scaffold TypeScript MCP package"
```

---

### Task 2: Define core types

**Files:**
- Create: `tools/xedit-mcp/src/types.ts`
- Create: `tools/xedit-mcp/tests/unit/types.test.ts` (compile-time assertions only)

**Rationale:** Lock the response envelope, rule/finding shapes, and MCP error-code namespace as the foundation everything else builds on. Types live in one file so the pipeline and tools share a single source of truth (spec §16).

- [ ] **Step 1: Write the failing test (compile-time discrimination check)**

```ts
// tests/unit/types.test.ts
import { describe, it, expect } from "vitest";
import type { Envelope, Rule, Finding, ToolContext } from "../../src/types.js";
import { MCP_ERROR_CODES } from "../../src/types.js";

describe("types", () => {
  it("MCP_ERROR_CODES contains required Batch 1 codes", () => {
    expect(MCP_ERROR_CODES.INVALID_REQUEST).toBe("invalid_request");
    expect(MCP_ERROR_CODES.STATE_VIOLATION).toBe("state_violation");
    expect(MCP_ERROR_CODES.DAEMON_ERROR).toBe("daemon_error");
    expect(MCP_ERROR_CODES.MCP_MODE_REQUIRED).toBe("mcp_mode_required");
  });

  it("Envelope discriminates ok=false vs ok=true at compile time", () => {
    const ok: Envelope = { ok: true, tool: "x", summary: "s", warnings: [] };
    const bad: Envelope = {
      ok: false, tool: "x", summary: "s", warnings: [],
      code: "invalid_request", hint: "h",
    };
    expect(ok.ok).toBe(true);
    expect(bad.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/types.test.ts
```

Expected: FAIL — module `../../src/types.js` not found.

- [ ] **Step 3: Implement `src/types.ts`**

```ts
// src/types.ts
export const MCP_ERROR_CODES = {
  INVALID_REQUEST: "invalid_request",
  STATE_VIOLATION: "state_violation",
  DAEMON_ERROR: "daemon_error",
  MCP_MODE_REQUIRED: "mcp_mode_required",
  SNAPSHOT_FAILED: "snapshot_failed",
  CONFIRM_REQUIRED: "confirm_required",
  CONFIRM_TOKEN_INVALID: "confirm_token_invalid",
  CONFIRM_TOKEN_EXPIRED: "confirm_token_expired",
} as const;

export type McpErrorCode =
  | (typeof MCP_ERROR_CODES)[keyof typeof MCP_ERROR_CODES]
  | `rule_${string}`;

export type Severity = "MEDIUM" | "HIGH" | "CRITICAL";

export interface Warning {
  code: string;
  message: string;
  severity: "MEDIUM" | "HIGH";
}

export interface ChangedSet {
  files: string[];
  records: string[];
  counts: { added: number; modified: number; deleted: number };
}

export type EnvelopeStatus =
  | "completed"
  | "pending_shutdown"
  | "partial"
  | "preview"
  | "refused";

export interface EnvelopeBase {
  tool: string;
  summary: string;
  warnings: Warning[];
}

export interface EnvelopeOk extends EnvelopeBase {
  ok: true;
  data?: unknown;
  changed?: ChangedSet;
  status?: EnvelopeStatus;
  snapshotId?: string;
  dirty?: { files: string[]; unsavedChangeCount: number };
  readback?: { kind: "snapshot" | "resource"; ref: string };
  preview?: { from: unknown; to: unknown; affected: unknown[] };
  confirmToken?: string;
  expiresAt?: string;
}

export interface EnvelopeRefusal extends EnvelopeBase {
  ok: false;
  code: McpErrorCode;
  severity?: Severity;
  hint?: string;
  rationale?: string;
  matched?: Record<string, unknown>;
  detail?: Record<string, unknown>;
}

export type Envelope = EnvelopeOk | EnvelopeRefusal;

export interface Finding {
  ruleId: string;
  matched: Record<string, unknown>;
  message: string;
}

export interface ToolContext {
  daemonPid?: number;
  loadOrder?: string[];
  consentEnabled?: boolean;
  mcpModeActive?: boolean;
  capabilities?: CapabilitiesSnapshot;
  /** Session id used for audit + future snapshot pathing. */
  sessionId: string;
}

export interface CapabilitiesSnapshot {
  contractVersion: string;
  gameMode: string;
  commands: string[];
  supports?: Record<string, unknown>;
  fetchedAt: string;
}

export interface Rule {
  id: string;
  appliesTo: string[];
  riskLevel: Severity;
  description: string;
  suggestion: string;
  rationale?: string;
  check: (input: {
    tool: string;
    args: Record<string, unknown>;
    ctx: ToolContext;
  }) => Finding | null;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/types.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/types.ts tools/xedit-mcp/tests/unit/types.test.ts
git commit -m "feat(xedit-mcp): define core types (envelope, rule, context, error codes)"
```

---

### Task 3: Implement the audit logger

**Files:**
- Create: `tools/xedit-mcp/src/audit.ts`
- Create: `tools/xedit-mcp/tests/unit/audit.test.ts`

**Rationale:** Pipeline stage [7] writes one JSONL line per tool call. Build this early because every later test will optionally exercise it. Per spec §16: `.opencode/artifacts/xedit-mcp/audit/YYYY-MM-DD.jsonl`. Logger is filesystem-agnostic (takes a base directory) so tests can use a temp dir.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/audit.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAuditLogger } from "../../src/audit.js";

describe("audit logger", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "xedit-mcp-audit-"));
  });

  it("writes one JSONL line per record under YYYY-MM-DD.jsonl", async () => {
    const logger = createAuditLogger({ baseDir: dir });
    await logger.append({
      tool: "xedit_session",
      argsHash: "abc123",
      decision: "ok",
      ok: true,
    });
    await logger.append({
      tool: "xedit_find_record",
      argsHash: "def456",
      decision: "refused",
      ok: false,
      code: "rule_LOAD001",
    });

    const today = new Date().toISOString().slice(0, 10);
    const filePath = join(dir, `${today}.jsonl`);
    expect(existsSync(filePath)).toBe(true);

    const lines = readFileSync(filePath, "utf8").trim().split("\n");
    expect(lines).toHaveLength(2);
    const first = JSON.parse(lines[0]);
    expect(first.tool).toBe("xedit_session");
    expect(first.ok).toBe(true);
    expect(typeof first.ts).toBe("string");
    const second = JSON.parse(lines[1]);
    expect(second.code).toBe("rule_LOAD001");
  });

  it("never throws on disk errors; surfaces via onError callback", async () => {
    const errors: unknown[] = [];
    const logger = createAuditLogger({
      baseDir: "/this/does/not/exist/and/cannot/be/created",
      onError: (e) => errors.push(e),
    });
    await logger.append({ tool: "x", argsHash: "h", decision: "ok", ok: true });
    expect(errors.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/audit.test.ts
```

Expected: FAIL — module `../../src/audit.js` not found.

- [ ] **Step 3: Implement `src/audit.ts`**

```ts
// src/audit.ts
import { mkdir, appendFile } from "node:fs/promises";
import { join } from "node:path";

export interface AuditRecord {
  tool: string;
  argsHash: string;
  decision: "ok" | "refused" | "warned";
  ok: boolean;
  code?: string;
  ruleHits?: string[];
  snapshotId?: string;
  daemonPid?: number;
  sessionId?: string;
}

export interface AuditLogger {
  append(record: AuditRecord): Promise<void>;
}

export interface AuditLoggerOptions {
  baseDir: string;
  onError?: (err: unknown) => void;
  /** Override clock for tests. */
  now?: () => Date;
}

export function createAuditLogger(opts: AuditLoggerOptions): AuditLogger {
  const now = opts.now ?? (() => new Date());
  const onError = opts.onError ?? (() => {});

  return {
    async append(record: AuditRecord) {
      const ts = now();
      const day = ts.toISOString().slice(0, 10);
      const line = JSON.stringify({ ts: ts.toISOString(), ...record }) + "\n";
      const filePath = join(opts.baseDir, `${day}.jsonl`);
      try {
        await mkdir(opts.baseDir, { recursive: true });
        await appendFile(filePath, line, "utf8");
      } catch (err) {
        onError(err);
      }
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/audit.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/audit.ts tools/xedit-mcp/tests/unit/audit.test.ts
git commit -m "feat(xedit-mcp): append-only JSONL audit logger"
```

---

### Task 4: Implement the envelope shaper

**Files:**
- Create: `tools/xedit-mcp/src/envelope.ts`
- Create: `tools/xedit-mcp/tests/unit/envelope.test.ts`

**Rationale:** Pipeline stage [7] guarantees the raw daemon envelope never leaks. Centralize ok/refusal/preview construction so every tool returns the identical shape (spec §16 schema).

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/envelope.test.ts
import { describe, it, expect } from "vitest";
import { ok, refuse, fromRuleFinding } from "../../src/envelope.js";

describe("envelope shaper", () => {
  it("ok() builds a minimal success envelope with empty warnings", () => {
    const e = ok({ tool: "xedit_session", summary: "ready" });
    expect(e.ok).toBe(true);
    expect(e.tool).toBe("xedit_session");
    expect(e.warnings).toEqual([]);
  });

  it("ok() passes through data, status, dirty", () => {
    const e = ok({
      tool: "xedit_read_record",
      summary: "1 record",
      data: { formId: "0x012345" },
      status: "completed",
    });
    if (!e.ok) throw new Error("expected ok");
    expect(e.data).toEqual({ formId: "0x012345" });
    expect(e.status).toBe("completed");
  });

  it("refuse() builds a refusal envelope with code + hint", () => {
    const e = refuse({
      tool: "xedit_find_record",
      summary: "blocked",
      code: "state_violation",
      hint: "load the file first",
    });
    expect(e.ok).toBe(false);
    if (e.ok) throw new Error("expected refusal");
    expect(e.code).toBe("state_violation");
    expect(e.hint).toBe("load the file first");
  });

  it("fromRuleFinding() maps a rule + finding to a rule_<id> refusal", () => {
    const e = fromRuleFinding(
      { tool: "xedit_find_record" },
      {
        id: "LOAD001",
        appliesTo: ["xedit_find_record"],
        riskLevel: "CRITICAL",
        description: "Target not in load order",
        suggestion: "add to plugins.txt first",
        check: () => null,
      },
      { ruleId: "LOAD001", matched: { file: "X.esp" }, message: "not loaded" },
    );
    if (e.ok) throw new Error("expected refusal");
    expect(e.code).toBe("rule_LOAD001");
    expect(e.severity).toBe("CRITICAL");
    expect(e.hint).toBe("add to plugins.txt first");
    expect(e.matched).toEqual({ file: "X.esp" });
    expect(e.status).toBe("refused");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/envelope.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/envelope.ts`**

```ts
// src/envelope.ts
import type {
  Envelope, EnvelopeOk, EnvelopeRefusal, Rule, Finding, Warning, McpErrorCode,
} from "./types.js";

export function ok(
  input: Omit<EnvelopeOk, "ok" | "warnings"> & { warnings?: Warning[] },
): EnvelopeOk {
  return { ok: true, warnings: input.warnings ?? [], ...input };
}

export function refuse(
  input: Omit<EnvelopeRefusal, "ok" | "warnings"> & { warnings?: Warning[] },
): EnvelopeRefusal {
  return {
    ok: false,
    warnings: input.warnings ?? [],
    ...input,
  };
}

export function fromRuleFinding(
  base: { tool: string },
  rule: Rule,
  finding: Finding,
): EnvelopeRefusal {
  return refuse({
    tool: base.tool,
    summary: `Refused by rule ${rule.id}: ${rule.description}`,
    code: `rule_${rule.id}` as McpErrorCode,
    severity: rule.riskLevel,
    hint: rule.suggestion,
    rationale: rule.rationale,
    matched: finding.matched,
    status: undefined,
  }) as EnvelopeRefusal & { status?: never } as EnvelopeRefusal;
}
```

> Note: `EnvelopeRefusal` does not carry `status`; the test asserts `status === "refused"`. Add `status` to the refusal shape OR have `fromRuleFinding` return it. Simplest: extend `EnvelopeRefusal` in `types.ts` to allow an optional `status?: "refused"` and set it here. Apply that small type change as part of this step:

```ts
// in src/types.ts, EnvelopeRefusal — add:
  status?: "refused";
```

and finalize `fromRuleFinding`:

```ts
export function fromRuleFinding(
  base: { tool: string },
  rule: Rule,
  finding: Finding,
): EnvelopeRefusal {
  return refuse({
    tool: base.tool,
    summary: `Refused by rule ${rule.id}: ${rule.description}`,
    code: `rule_${rule.id}` as McpErrorCode,
    severity: rule.riskLevel,
    hint: rule.suggestion,
    rationale: rule.rationale,
    matched: finding.matched,
    status: "refused",
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/envelope.test.ts
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/envelope.ts tools/xedit-mcp/src/types.ts tools/xedit-mcp/tests/unit/envelope.test.ts
git commit -m "feat(xedit-mcp): standard envelope shaper (ok/refuse/fromRuleFinding)"
```

---

## Phase B — Daemon Adapter & Session Lifecycle

### Task 5: Implement the daemon adapter over `xedit-client.ps1`

**Files:**
- Create: `tools/xedit-mcp/src/daemon-adapter.ts`
- Create: `tools/xedit-mcp/tests/fixtures/daemon-mock.ts`
- Create: `tools/xedit-mcp/tests/unit/daemon-adapter.test.ts`

**Rationale:** The MCP must NOT re-implement launch/PID/automation-call plumbing — it shells out to the existing `tools/mo2-vfs-launcher/xedit-client.ps1` (spec §3). The adapter is the single seam where TS meets PowerShell; it is injectable so unit tests can substitute an in-memory mock and only the integration test hits the real client.

- [ ] **Step 1: Write the fixture mock**

```ts
// tests/fixtures/daemon-mock.ts
import type { DaemonCall, DaemonAdapter } from "../../src/daemon-adapter.js";

/** In-memory adapter: maps command -> canned daemon result envelope. */
export function makeMockAdapter(
  handlers: Record<string, (args: Record<string, unknown>) => unknown>,
): DaemonAdapter {
  return {
    async call({ command, args }: DaemonCall) {
      const h = handlers[command];
      if (!h) {
        return {
          ok: false,
          command,
          error: { code: "unknown_command", message: `no mock for ${command}` },
        };
      }
      return { ok: true, command, result: h(args ?? {}) };
    },
  };
}
```

- [ ] **Step 2: Write the failing test**

```ts
// tests/unit/daemon-adapter.test.ts
import { describe, it, expect } from "vitest";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("daemon adapter (mock contract)", () => {
  it("returns the raw native ok envelope for a known command", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
    });
    const res = await adapter.call({ command: "system.describe", args: {} });
    expect(res.ok).toBe(true);
    if (!res.ok) throw new Error("expected ok");
    expect((res.result as { gameMode: string }).gameMode).toBe("Fallout4");
  });

  it("returns a native error envelope for an unknown command", async () => {
    const adapter = makeMockAdapter({});
    const res = await adapter.call({ command: "nope.nope", args: {} });
    expect(res.ok).toBe(false);
    if (res.ok) throw new Error("expected error");
    expect(res.error.code).toBe("unknown_command");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
npm test -- tests/unit/daemon-adapter.test.ts
```

Expected: FAIL — `../../src/daemon-adapter.js` not found.

- [ ] **Step 4: Implement `src/daemon-adapter.ts`**

```ts
// src/daemon-adapter.ts
import { spawn } from "node:child_process";
import { writeFile, readFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

export interface DaemonCall {
  command: string;
  args?: Record<string, unknown>;
  requestId?: string;
}

export type NativeEnvelope =
  | { ok: true; command: string; requestId?: string; result: unknown }
  | { ok: false; command: string; requestId?: string; error: { code: string; message: string; details?: unknown } };

export interface DaemonAdapter {
  call(call: DaemonCall): Promise<NativeEnvelope>;
}

export interface PowershellAdapterOptions {
  /** Absolute path to xedit-client.ps1 */
  clientScript: string;
  /** Daemon PID to target with -automation-call-pid */
  pid: number;
  /** Optional mcp token to inject into every request (Batch 1: sent, daemon may ignore). */
  mcpToken?: string;
  /** Override the working directory for temp request/response files. */
  scratchDir?: string;
  pwshExe?: string;
}

/**
 * Production adapter: invokes `xedit-client.ps1 automation call` with file-based
 * request/response, exactly as tools/mo2-vfs-launcher/lib/xedit-client.call.ps1 expects.
 */
export function createPowershellAdapter(opts: PowershellAdapterOptions): DaemonAdapter {
  const pwsh = opts.pwshExe ?? "pwsh";
  return {
    async call({ command, args, requestId }: DaemonCall): Promise<NativeEnvelope> {
      const scratch = opts.scratchDir ?? join(tmpdir(), "xedit-mcp-calls");
      await mkdir(scratch, { recursive: true });
      const id = requestId ?? randomUUID();
      const reqPath = join(scratch, `${id}.req.json`);
      const resPath = join(scratch, `${id}.res.json`);
      const request: Record<string, unknown> = { command, args: args ?? {}, requestId: id };
      if (opts.mcpToken) request.mcpToken = opts.mcpToken;
      await writeFile(reqPath, JSON.stringify(request), "utf8");

      await runPwsh(pwsh, [
        "-NoProfile", "-File", opts.clientScript,
        "automation", "call",
        "--pid", String(opts.pid),
        "--request", reqPath,
        "--response", resPath,
      ]);

      const raw = await readFile(resPath, "utf8");
      return JSON.parse(raw) as NativeEnvelope;
    },
  };
}

function runPwsh(pwsh: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(pwsh, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`xedit-client.ps1 exited ${code}: ${stderr.slice(0, 500)}`));
    });
  });
}
```

> The exact `automation call` flag names (`--pid`/`--request`/`--response`) MUST be confirmed against `tools/mo2-vfs-launcher/lib/xedit-client.call.ps1` during implementation. Reconnaissance reported the call path uses `-automation-call-pid:/-request:/-response:` internally; align the outer-client CLI flags to whatever `xedit-client.ps1` actually parses. If they differ, adjust this adapter — the mock-based unit tests are unaffected.

- [ ] **Step 5: Run test to verify it passes**

```bash
npm test -- tests/unit/daemon-adapter.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add tools/xedit-mcp/src/daemon-adapter.ts tools/xedit-mcp/tests/fixtures/daemon-mock.ts tools/xedit-mcp/tests/unit/daemon-adapter.test.ts
git commit -m "feat(xedit-mcp): daemon adapter over xedit-client.ps1 + in-memory mock"
```

---

### Task 6: Implement session lifecycle (ensure-ready, describe, capabilities fetch)

**Files:**
- Create: `tools/xedit-mcp/src/session.ts`
- Create: `tools/xedit-mcp/tests/unit/session.test.ts`

**Rationale:** Builds the `ToolContext` (daemon up, load order, consent, capabilities) that pipeline stage [2] and the rule registry consume. Uses the adapter from Task 5. Launch orchestration (process launch + wait-ready) is delegated to `xedit-client.ps1 process launch`; this module owns the post-launch handshake (`system.describe` + `system.capabilities`).

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/session.test.ts
import { describe, it, expect } from "vitest";
import { buildContext } from "../../src/session.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("session.buildContext", () => {
  it("populates capabilities + load order from describe/capabilities", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/FO4/Data" }),
      "system.capabilities": () => ({
        contractVersion: "0.10",
        commands: ["records.get", "records.conflict_status"],
        supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s1" });
    expect(ctx.capabilities?.contractVersion).toBe("0.10");
    expect(ctx.capabilities?.gameMode).toBe("Fallout4");
    expect(ctx.loadOrder).toContain("MyPatch.esp");
    expect(ctx.consentEnabled).toBe(true);
    expect(ctx.sessionId).toBe("s1");
  });

  it("sets consentEnabled=false when capability flag absent", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({ contractVersion: "0.10", commands: [], supports: {} }),
      "files.list": () => ({ files: [] }),
    });
    const ctx = await buildContext({ adapter, sessionId: "s2" });
    expect(ctx.consentEnabled).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/session.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/session.ts`**

```ts
// src/session.ts
import type { DaemonAdapter } from "./daemon-adapter.js";
import type { ToolContext, CapabilitiesSnapshot } from "./types.js";

export interface BuildContextOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export async function buildContext(opts: BuildContextOptions): Promise<ToolContext> {
  const { adapter, sessionId } = opts;

  const describeRes = await adapter.call({ command: "system.describe", args: {} });
  const capsRes = await adapter.call({ command: "system.capabilities", args: {} });
  const filesRes = await adapter.call({ command: "files.list", args: {} });

  const describe = describeRes.ok ? (describeRes.result as Record<string, unknown>) : {};
  const caps = capsRes.ok ? (capsRes.result as Record<string, unknown>) : {};
  const files = filesRes.ok ? (filesRes.result as { files?: string[] }) : { files: [] };

  const supports = (caps.supports ?? {}) as Record<string, unknown>;

  const capabilities: CapabilitiesSnapshot = {
    contractVersion: String(caps.contractVersion ?? "unknown"),
    gameMode: String(describe.gameMode ?? "unknown"),
    commands: Array.isArray(caps.commands) ? (caps.commands as string[]) : [],
    supports,
    fetchedAt: new Date().toISOString(),
  };

  return {
    sessionId,
    daemonPid: opts.daemonPid,
    mcpModeActive: opts.mcpModeActive ?? false,
    loadOrder: files.files ?? [],
    consentEnabled: supports.iKnowWhatImDoing === true,
    capabilities,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/session.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/session.ts tools/xedit-mcp/tests/unit/session.test.ts
git commit -m "feat(xedit-mcp): session lifecycle builds ToolContext from describe/capabilities/files"
```

---

## Phase C — Pipeline Stages

### Task 7: Pipeline stage [1] — schema validator

**Files:**
- Create: `tools/xedit-mcp/src/pipeline/validate.ts`
- Create: `tools/xedit-mcp/tests/unit/validate.test.ts`

**Rationale:** First gate. Uses `zod` schemas declared per-tool so refusals carry actionable `detail: { field, expected, got }`. Refusal shape is the agent-readable hint pattern from instrMCP (spec §6).

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/validate.test.ts
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { validateArgs } from "../../src/pipeline/validate.js";

const schema = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^0x[0-9a-fA-F]{8}$/),
});

describe("pipeline.validate", () => {
  it("returns null on a fully valid args object", () => {
    const r = validateArgs(schema, { file: "X.esp", formId: "0x00001234" });
    expect(r).toBeNull();
  });

  it("returns a refusal envelope with detail on bad shape", () => {
    const r = validateArgs(schema, { file: "", formId: "nope" }, { tool: "xedit_find_record" });
    expect(r).not.toBeNull();
    if (!r) throw new Error("expected refusal");
    expect(r.ok).toBe(false);
    if (r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("invalid_request");
    expect(r.detail).toBeDefined();
    expect(r.tool).toBe("xedit_find_record");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/validate.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/pipeline/validate.ts`**

```ts
// src/pipeline/validate.ts
import type { ZodTypeAny } from "zod";
import type { EnvelopeRefusal } from "../types.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

export function validateArgs(
  schema: ZodTypeAny,
  args: unknown,
  meta: { tool: string } = { tool: "unknown" },
): EnvelopeRefusal | null {
  const result = schema.safeParse(args);
  if (result.success) return null;
  const issues = result.error.issues.map((i) => ({
    path: i.path.join("."),
    expected: i.message,
    code: i.code,
  }));
  return refuse({
    tool: meta.tool,
    summary: "Argument validation failed",
    code: MCP_ERROR_CODES.INVALID_REQUEST,
    hint: "Fix the listed fields and retry.",
    detail: { issues },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/validate.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/pipeline/validate.ts tools/xedit-mcp/tests/unit/validate.test.ts
git commit -m "feat(xedit-mcp): pipeline stage [1] zod-based schema validator"
```

---

### Task 8: Pipeline stage [2] — state precheck

**Files:**
- Create: `tools/xedit-mcp/src/pipeline/state-precheck.ts`
- Create: `tools/xedit-mcp/tests/unit/state-precheck.test.ts`

**Rationale:** Confirms daemon/load-order/consent/mcp-mode preconditions. Per-tool "needs" declared as a small descriptor (e.g. `{ needsDaemon: true, needsConsent: true }`) so each tool can opt into only the checks it requires.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/state-precheck.test.ts
import { describe, it, expect } from "vitest";
import { precheck } from "../../src/pipeline/state-precheck.js";
import type { ToolContext } from "../../src/types.js";

const baseCtx: ToolContext = {
  sessionId: "s1",
  daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  consentEnabled: false,
  mcpModeActive: false,
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("pipeline.precheck", () => {
  it("passes when no needs are declared", () => {
    const r = precheck({ tool: "t" }, { ctx: baseCtx, needs: {} });
    expect(r).toBeNull();
  });

  it("refuses if needsDaemon and pid is absent", () => {
    const r = precheck({ tool: "t" }, { ctx: { ...baseCtx, daemonPid: undefined }, needs: { daemon: true } });
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("state_violation");
    expect(r.hint).toContain("daemon");
  });

  it("refuses if needsConsent and consent flag is off", () => {
    const r = precheck({ tool: "t" }, { ctx: { ...baseCtx, consentEnabled: false }, needs: { consent: true } });
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("state_violation");
    expect(r.hint).toContain("IKnowWhatImDoing");
  });

  it("refuses if needsTargetLoaded and file not in load order", () => {
    const r = precheck(
      { tool: "t", args: { file: "Missing.esp" } },
      { ctx: baseCtx, needs: { targetFileFromArg: "file" } },
    );
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("state_violation");
    expect(r.hint).toContain("load order");
  });

  it("passes targetFileFromArg when file is loaded", () => {
    const r = precheck(
      { tool: "t", args: { file: "Patch.esp" } },
      { ctx: baseCtx, needs: { targetFileFromArg: "file" } },
    );
    expect(r).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/state-precheck.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/pipeline/state-precheck.ts`**

```ts
// src/pipeline/state-precheck.ts
import type { EnvelopeRefusal, ToolContext } from "../types.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

export interface PrecheckNeeds {
  daemon?: boolean;
  consent?: boolean;
  /** Name of the args field whose string value must be present in ctx.loadOrder. */
  targetFileFromArg?: string;
}

export function precheck(
  call: { tool: string; args?: Record<string, unknown> },
  input: { ctx: ToolContext; needs: PrecheckNeeds },
): EnvelopeRefusal | null {
  const { ctx, needs } = input;

  if (needs.daemon && !ctx.daemonPid) {
    return refuse({
      tool: call.tool,
      summary: "Daemon not ready",
      code: MCP_ERROR_CODES.STATE_VIOLATION,
      hint: "Call xedit_session first to ensure the daemon is running.",
    });
  }

  if (needs.consent && !ctx.consentEnabled) {
    return refuse({
      tool: call.tool,
      summary: "Consent flag not active",
      code: MCP_ERROR_CODES.STATE_VIOLATION,
      hint: "Relaunch daemon with -IKnowWhatImDoing to enable mutating ops.",
    });
  }

  if (needs.targetFileFromArg) {
    const file = (call.args ?? {})[needs.targetFileFromArg];
    if (typeof file === "string" && !(ctx.loadOrder ?? []).includes(file)) {
      return refuse({
        tool: call.tool,
        summary: `Target file not in active load order: ${file}`,
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Add the file to plugins.txt and reload the session first.",
        detail: { file, loadOrder: ctx.loadOrder ?? [] },
      });
    }
  }

  return null;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/state-precheck.test.ts
```

Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/pipeline/state-precheck.ts tools/xedit-mcp/tests/unit/state-precheck.test.ts
git commit -m "feat(xedit-mcp): pipeline stage [2] state precheck (daemon/consent/load-order)"
```

---

### Task 9: Pipeline stage [3] — rule registry + first seed rule LOAD001

**Files:**
- Create: `tools/xedit-mcp/src/rules/registry.ts`
- Create: `tools/xedit-mcp/src/rules/LOAD001.ts`
- Create: `tools/xedit-mcp/src/pipeline/rules.ts`
- Create: `tools/xedit-mcp/tests/unit/rules.test.ts`
- Create: `tools/xedit-mcp/tests/unit/LOAD001.test.ts`

**Rationale:** Decoupled rules — one file per rule under `src/rules/`. Registry indexes by `appliesTo`. Only `LOAD001` is fully implemented in Batch 1; remaining 9 seed rules from spec §6 land alongside the tools that trigger them in later batches.

- [ ] **Step 1: Write the failing tests**

```ts
// tests/unit/LOAD001.test.ts
import { describe, it, expect } from "vitest";
import { LOAD001 } from "../../src/rules/LOAD001.js";
import type { ToolContext } from "../../src/types.js";

const ctx: ToolContext = {
  sessionId: "s",
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("rule LOAD001", () => {
  it("appliesTo includes the Batch 1 read tools", () => {
    expect(LOAD001.appliesTo).toEqual(
      expect.arrayContaining(["xedit_find_record", "xedit_read_record", "xedit_inspect_conflicts"]),
    );
  });

  it("returns null when target file is loaded", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: { file: "Patch.esp" }, ctx });
    expect(f).toBeNull();
  });

  it("returns a Finding when target file is not loaded", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: { file: "Ghost.esp" }, ctx });
    expect(f).not.toBeNull();
    expect(f!.ruleId).toBe("LOAD001");
    expect(f!.matched.file).toBe("Ghost.esp");
  });

  it("returns null when no file arg is present (rule is targeted)", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: {}, ctx });
    expect(f).toBeNull();
  });
});
```

```ts
// tests/unit/rules.test.ts
import { describe, it, expect } from "vitest";
import { createRegistry } from "../../src/rules/registry.js";
import { runRules } from "../../src/pipeline/rules.js";
import type { Rule, ToolContext } from "../../src/types.js";

const exampleRule: Rule = {
  id: "TEST001",
  appliesTo: ["xedit_x"],
  riskLevel: "HIGH",
  description: "test",
  suggestion: "fix it",
  check: ({ args }) => (args.bad ? { ruleId: "TEST001", matched: {}, message: "bad" } : null),
};

const ctx: ToolContext = {
  sessionId: "s",
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("pipeline.rules", () => {
  it("registry returns rules for a matching tool only", () => {
    const reg = createRegistry([exampleRule]);
    expect(reg.forTool("xedit_x")).toHaveLength(1);
    expect(reg.forTool("xedit_y")).toHaveLength(0);
  });

  it("runRules returns null when nothing trips", async () => {
    const reg = createRegistry([exampleRule]);
    const r = await runRules({ tool: "xedit_x", args: {}, ctx, registry: reg });
    expect(r).toBeNull();
  });

  it("runRules returns a refusal envelope when a CRITICAL/HIGH rule trips", async () => {
    const reg = createRegistry([exampleRule]);
    const r = await runRules({ tool: "xedit_x", args: { bad: true }, ctx, registry: reg });
    expect(r).not.toBeNull();
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("rule_TEST001");
    expect(r.severity).toBe("HIGH");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm test -- tests/unit/LOAD001.test.ts tests/unit/rules.test.ts
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `src/rules/LOAD001.ts`**

```ts
// src/rules/LOAD001.ts
import type { Rule } from "../types.js";

export const LOAD001: Rule = {
  id: "LOAD001",
  appliesTo: [
    "xedit_find_record",
    "xedit_read_record",
    "xedit_inspect_conflicts",
    "xedit_call",
  ],
  riskLevel: "CRITICAL",
  description: "Target file is not in the active load order.",
  suggestion: "Add the file to plugins.txt and reload the session first.",
  rationale:
    "Operations against an unloaded file silently miss records and produce false-negative conflict reports.",
  check({ args, ctx }) {
    const file = typeof args.file === "string" ? args.file : undefined;
    if (!file) return null;
    const loadOrder = ctx.loadOrder ?? [];
    if (loadOrder.includes(file)) return null;
    return {
      ruleId: "LOAD001",
      matched: { file, loadOrderSize: loadOrder.length },
      message: `File ${file} not in load order`,
    };
  },
};
```

- [ ] **Step 4: Implement `src/rules/registry.ts`**

```ts
// src/rules/registry.ts
import type { Rule } from "../types.js";
import { LOAD001 } from "./LOAD001.js";

export interface Registry {
  forTool(tool: string): Rule[];
  all(): Rule[];
}

export function createRegistry(rules: Rule[]): Registry {
  const index = new Map<string, Rule[]>();
  for (const r of rules) {
    for (const t of r.appliesTo) {
      const arr = index.get(t) ?? [];
      arr.push(r);
      index.set(t, arr);
    }
  }
  return {
    forTool: (tool) => index.get(tool) ?? [],
    all: () => [...rules],
  };
}

/** Default registry — wire all real seed rules here as they land. Batch 1: LOAD001 only. */
export function defaultRegistry(): Registry {
  return createRegistry([LOAD001]);
}
```

- [ ] **Step 5: Implement `src/pipeline/rules.ts`**

```ts
// src/pipeline/rules.ts
import type { EnvelopeRefusal, ToolContext } from "../types.js";
import { fromRuleFinding } from "../envelope.js";
import type { Registry } from "../rules/registry.js";

export interface RunRulesInput {
  tool: string;
  args: Record<string, unknown>;
  ctx: ToolContext;
  registry: Registry;
  /** Block HIGH (default true); CRITICAL always blocks; MEDIUM always warns only. */
  blockHigh?: boolean;
}

export async function runRules(input: RunRulesInput): Promise<EnvelopeRefusal | null> {
  const blockHigh = input.blockHigh ?? true;
  const rules = input.registry.forTool(input.tool);
  for (const rule of rules) {
    const finding = rule.check({ tool: input.tool, args: input.args, ctx: input.ctx });
    if (!finding) continue;
    if (rule.riskLevel === "CRITICAL" || (rule.riskLevel === "HIGH" && blockHigh)) {
      return fromRuleFinding({ tool: input.tool }, rule, finding);
    }
    // MEDIUM (and HIGH when blockHigh=false) fall through; the caller is expected to
    // collect them as warnings via a separate pass. For Batch 1 we keep this simple.
  }
  return null;
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
npm test -- tests/unit/LOAD001.test.ts tests/unit/rules.test.ts
```

Expected: PASS — 4 + 3 = 7 tests.

- [ ] **Step 7: Commit**

```bash
git add tools/xedit-mcp/src/rules/ tools/xedit-mcp/src/pipeline/rules.ts tools/xedit-mcp/tests/unit/LOAD001.test.ts tools/xedit-mcp/tests/unit/rules.test.ts
git commit -m "feat(xedit-mcp): pipeline stage [3] rule registry + LOAD001 seed"
```

---

### Task 10: Pipeline stage [6] — forward to daemon, map errors

**Files:**
- Create: `tools/xedit-mcp/src/pipeline/forward.ts`
- Create: `tools/xedit-mcp/tests/unit/forward.test.ts`

**Rationale:** Wraps a single daemon adapter call, translates native error envelopes into MCP refusals, and surfaces `mcp_mode_required` distinctly so callers can detect the bypass-closure case. Raw native envelopes never leak.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/forward.test.ts
import { describe, it, expect } from "vitest";
import { forwardCall } from "../../src/pipeline/forward.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("pipeline.forward", () => {
  it("returns ok envelope when daemon returns ok", async () => {
    const adapter = makeMockAdapter({
      "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
    });
    const env = await forwardCall({
      tool: "xedit_read_record",
      command: "records.get",
      args: { file: "X.esp", formId: "0x012345" },
      adapter,
      summary: "1 record",
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({ formId: "0x012345" });
  });

  it("maps daemon error to refusal with code=daemon_error", async () => {
    const adapter = makeMockAdapter({}); // unknown_command path
    const env = await forwardCall({
      tool: "xedit_call",
      command: "records.bogus",
      args: {},
      adapter,
      summary: "fail",
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("daemon_error");
    expect(env.detail).toMatchObject({ daemonCode: "unknown_command" });
  });

  it("maps mcp_mode_required distinctly", async () => {
    const adapter = makeMockAdapter({});
    // override behavior: return mcp_mode_required for any call
    const wrapped = {
      async call(c: { command: string; args?: Record<string, unknown> }) {
        return {
          ok: false as const, command: c.command,
          error: { code: "mcp_mode_required", message: "need token" },
        };
      },
    };
    const env = await forwardCall({
      tool: "xedit_session",
      command: "system.describe",
      args: {},
      adapter: wrapped,
      summary: "describe",
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("mcp_mode_required");
    expect(env.hint).toContain("token");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/forward.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/pipeline/forward.ts`**

```ts
// src/pipeline/forward.ts
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { Envelope } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

export interface ForwardInput {
  tool: string;
  command: string;
  args: Record<string, unknown>;
  adapter: DaemonAdapter;
  summary: string;
  /** Optional response post-processor (token shaping, projection). */
  shape?: (result: unknown) => unknown;
}

export async function forwardCall(input: ForwardInput): Promise<Envelope> {
  const native = await input.adapter.call({ command: input.command, args: input.args });
  if (native.ok) {
    return okEnv({
      tool: input.tool,
      summary: input.summary,
      data: input.shape ? input.shape(native.result) : native.result,
      status: "completed",
    });
  }
  if (native.error.code === "mcp_mode_required") {
    return refuse({
      tool: input.tool,
      summary: "Daemon refused: MCP-only mode active, token required",
      code: MCP_ERROR_CODES.MCP_MODE_REQUIRED,
      hint: "The daemon is in MCP-only mode. Ensure the MCP server provisioned a valid token at launch.",
      detail: { daemonMessage: native.error.message },
    });
  }
  return refuse({
    tool: input.tool,
    summary: `Daemon error: ${native.error.code}`,
    code: MCP_ERROR_CODES.DAEMON_ERROR,
    hint: native.error.message,
    detail: { daemonCode: native.error.code, daemonDetails: native.error.details },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/forward.test.ts
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/pipeline/forward.ts tools/xedit-mcp/tests/unit/forward.test.ts
git commit -m "feat(xedit-mcp): pipeline stage [6] forward to daemon + error mapping"
```

---

### Task 11: Pipeline composer — `runTool` wires [1] → [2] → [3] → [6] → [7]

**Files:**
- Create: `tools/xedit-mcp/src/pipeline/compose.ts`
- Create: `tools/xedit-mcp/tests/unit/compose.test.ts`

**Rationale:** Single entry point that every tool calls so the harness is uniform. Tools provide a `ToolSpec` (schema, needs, command, summary builder); the composer runs the stages in order and short-circuits on the first refusal.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/compose.test.ts
import { describe, it, expect } from "vitest";
import { z } from "zod";
import { runTool, type ToolSpec } from "../../src/pipeline/compose.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const adapter = makeMockAdapter({
  "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
});

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  loadOrder: ["Patch.esp"],
  consentEnabled: false,
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

const spec: ToolSpec = {
  name: "xedit_read_record",
  schema: z.object({ file: z.string(), formId: z.string() }),
  needs: { daemon: true, targetFileFromArg: "file" },
  command: "records.get",
  summary: (args) => `record ${String(args.formId)}`,
};

describe("pipeline.compose.runTool", () => {
  const auditDir = mkdtempSync(join(tmpdir(), "xedit-mcp-compose-"));
  const audit = createAuditLogger({ baseDir: auditDir });
  const registry = defaultRegistry();

  it("returns ok envelope on the happy path and writes audit", async () => {
    const env = await runTool(spec, {
      args: { file: "Patch.esp", formId: "0x012345" },
      ctx, adapter, registry, audit,
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({ formId: "0x012345" });
  });

  it("short-circuits on invalid args (stage 1)", async () => {
    const env = await runTool(spec, {
      args: { file: "Patch.esp" }, // missing formId
      ctx, adapter, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("short-circuits on state precheck (stage 2)", async () => {
    const env = await runTool(spec, {
      args: { file: "Ghost.esp", formId: "0x012345" },
      ctx, adapter, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("state_violation");
  });

  it("short-circuits on rule (stage 3) — LOAD001 against xedit_find_record", async () => {
    const findSpec: ToolSpec = {
      name: "xedit_find_record",
      schema: z.object({ file: z.string() }),
      needs: {}, // skip stage 2 so we exercise stage 3 specifically
      command: "records.list",
      summary: () => "list",
    };
    const a2 = makeMockAdapter({ "records.list": () => ({ records: [] }) });
    const env = await runTool(findSpec, {
      args: { file: "Ghost.esp" },
      ctx, adapter: a2, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/compose.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/pipeline/compose.ts`**

```ts
// src/pipeline/compose.ts
import type { ZodTypeAny } from "zod";
import type { Envelope, ToolContext } from "../types.js";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import { validateArgs } from "./validate.js";
import { precheck, type PrecheckNeeds } from "./state-precheck.js";
import { runRules } from "./rules.js";
import { forwardCall } from "./forward.js";
import { createHash } from "node:crypto";

export interface ToolSpec {
  name: string;
  schema: ZodTypeAny;
  needs: PrecheckNeeds;
  /** Native daemon command this tool primarily wraps. */
  command: string;
  /** Build the human-readable summary string from the (validated) args. */
  summary: (args: Record<string, unknown>) => string;
  /** Optional post-processor for the daemon result before envelope. */
  shape?: (result: unknown) => unknown;
}

export interface RunToolInput {
  args: Record<string, unknown>;
  ctx: ToolContext;
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
}

export async function runTool(spec: ToolSpec, input: RunToolInput): Promise<Envelope> {
  const argsHash = hashArgs(input.args);
  const meta = { tool: spec.name };

  const v = validateArgs(spec.schema, input.args, meta);
  if (v) {
    await input.audit.append({ tool: spec.name, argsHash, decision: "refused", ok: false, code: v.code });
    return v;
  }

  const p = precheck({ tool: spec.name, args: input.args }, { ctx: input.ctx, needs: spec.needs });
  if (p) {
    await input.audit.append({ tool: spec.name, argsHash, decision: "refused", ok: false, code: p.code });
    return p;
  }

  const r = await runRules({ tool: spec.name, args: input.args, ctx: input.ctx, registry: input.registry });
  if (r) {
    await input.audit.append({
      tool: spec.name, argsHash, decision: "refused", ok: false, code: r.code,
      ruleHits: [r.code.replace(/^rule_/, "")],
    });
    return r;
  }

  const env = await forwardCall({
    tool: spec.name,
    command: spec.command,
    args: input.args,
    adapter: input.adapter,
    summary: spec.summary(input.args),
    shape: spec.shape,
  });

  await input.audit.append({
    tool: spec.name, argsHash, decision: env.ok ? "ok" : "refused", ok: env.ok,
    code: env.ok ? undefined : env.code,
    daemonPid: input.ctx.daemonPid, sessionId: input.ctx.sessionId,
  });
  return env;
}

function hashArgs(args: Record<string, unknown>): string {
  return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/compose.test.ts
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/pipeline/compose.ts tools/xedit-mcp/tests/unit/compose.test.ts
git commit -m "feat(xedit-mcp): pipeline composer wires stages [1][2][3][6][7]"
```

---

## Phase D — Tools

### Task 12: Curated capabilities digest (static data)

**Files:**
- Create: `tools/xedit-mcp/src/capabilities-digest.ts`
- Create: `tools/xedit-mcp/tests/unit/capabilities-digest.test.ts`

**Rationale:** Per spec §9, the digest is the "open the toolbox without reading 35 KB" pattern. It is the same 47-command/8-group map the hub skill references, in machine form so `xedit_list_capabilities` can cross-check the live daemon at runtime and surface drift.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/capabilities-digest.test.ts
import { describe, it, expect } from "vitest";
import { CAPABILITIES_DIGEST, allDigestCommands } from "../../src/capabilities-digest.js";

describe("capabilities digest", () => {
  it("covers all 8 groups", () => {
    const groups = new Set(CAPABILITIES_DIGEST.groups.map((g) => g.name));
    expect(groups).toEqual(
      new Set(["system", "session", "files", "records", "elements", "jobs", "scripts"]),
    );
    // Note: 8 in spec includes "file hygiene" as a sub-area of files; we keep 7 top-level groups.
    expect(CAPABILITIES_DIGEST.groups.length).toBeGreaterThanOrEqual(7);
  });

  it("enumerates the read-only commands needed for Batch 1 (W2 conflict audit)", () => {
    const cmds = new Set(allDigestCommands());
    [
      "system.describe", "system.capabilities",
      "session.get_dirty_state",
      "records.list", "records.find_by_form_id", "records.find_by_editor_id",
      "records.get", "records.winning_override", "records.base_record",
      "records.conflict_status", "records.references", "records.referenced_by",
      "elements.get", "elements.children", "elements.conflict_status",
    ].forEach((c) => expect(cmds.has(c)).toBe(true));
  });

  it("each entry carries minimal metadata for skill use", () => {
    const sample = CAPABILITIES_DIGEST.groups[0].commands[0];
    expect(typeof sample.name).toBe("string");
    expect(typeof sample.summary).toBe("string");
    expect(typeof sample.mutating).toBe("boolean");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/capabilities-digest.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/capabilities-digest.ts`**

```ts
// src/capabilities-digest.ts
export interface DigestCommand {
  name: string;
  summary: string;
  mutating: boolean;
  /** Argument names that matter most; not a full schema. */
  keyArgs?: string[];
}

export interface DigestGroup {
  name: string;
  blurb: string;
  commands: DigestCommand[];
}

export interface CapabilitiesDigest {
  contractVersionExpected: string;
  groups: DigestGroup[];
}

export const CAPABILITIES_DIGEST: CapabilitiesDigest = {
  contractVersionExpected: "0.10",
  groups: [
    {
      name: "system",
      blurb: "Handshake & capability discovery; always available, no load required.",
      commands: [
        { name: "system.ping", summary: "Liveness check", mutating: false },
        { name: "system.describe", summary: "App / game mode / data path", mutating: false },
        { name: "system.capabilities", summary: "Live command list + supports.* tree", mutating: false },
      ],
    },
    {
      name: "session",
      blurb: "Dirty state, GUI blockers, save, navigate.",
      commands: [
        { name: "session.get_dirty_state", summary: "Which files have unsaved changes", mutating: false },
        { name: "session.get_gui_snapshot", summary: "Modal blocker probe", mutating: false },
        { name: "session.save", summary: "Save listed files; watch pendingShutdown", mutating: true, keyArgs: ["files"] },
        { name: "session.navigate_to_record", summary: "Drive GUI JumpTo", mutating: false, keyArgs: ["file", "formId"] },
      ],
    },
    {
      name: "files",
      blurb: "List/get/create plugins; header & masters hygiene.",
      commands: [
        { name: "files.list", summary: "List loaded files", mutating: false },
        { name: "files.get", summary: "Per-file summary", mutating: false, keyArgs: ["file"] },
        { name: "files.create", summary: "New plugin", mutating: true, keyArgs: ["name", "extension", "flags"] },
        { name: "files.add_required_masters", summary: "Add masters to a plugin", mutating: true, keyArgs: ["file", "masters"] },
        { name: "files.get_header", summary: "Read plugin header", mutating: false, keyArgs: ["file"] },
        { name: "files.get_masters", summary: "Read master list", mutating: false, keyArgs: ["file"] },
        { name: "files.set_header_flags", summary: "ESM/ESL flag toggle", mutating: true, keyArgs: ["file", "flags"] },
        { name: "files.sort_masters", summary: "Sort masters", mutating: true, keyArgs: ["file"] },
        { name: "files.clean_masters", summary: "Drop unused masters", mutating: true, keyArgs: ["file"] },
      ],
    },
    {
      name: "records",
      blurb: "Read/search + mutating create/copy/delete/mark_deleted (15 commands).",
      commands: [
        { name: "records.list", summary: "List records in a file/group", mutating: false, keyArgs: ["file", "signature"] },
        { name: "records.apply_filter", summary: "Server-side filter", mutating: false },
        { name: "records.base_record", summary: "Master record of an override", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.find_by_form_id", summary: "Locate by FormID", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.find_by_editor_id", summary: "Locate by EditorID", mutating: false, keyArgs: ["editorId"] },
        { name: "records.get", summary: "Get a record + fields", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.master_or_self", summary: "Resolve to master or self", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.winning_override", summary: "Which file wins for this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.conflict_status", summary: "Conflict label for a record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.references", summary: "Refs out from this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.referenced_by", summary: "Refs in to this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.create", summary: "Create record (signature support is dynamic)", mutating: true, keyArgs: ["file", "signature"] },
        { name: "records.copy_into", summary: "Copy as override into target plugin", mutating: true, keyArgs: ["sourceFile", "formId", "targetFile"] },
        { name: "records.delete", summary: "Delete record", mutating: true, keyArgs: ["file", "formId"] },
        { name: "records.mark_deleted", summary: "Mark deleted flag", mutating: true, keyArgs: ["file", "formId"] },
      ],
    },
    {
      name: "elements",
      blurb: "Read/write sub-record element tree (8 commands).",
      commands: [
        { name: "elements.get", summary: "Get element value/struct", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.children", summary: "List children at path", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.conflict_status", summary: "Element-level conflict", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.required_masters", summary: "Masters required by this element", mutating: false },
        { name: "elements.set_value", summary: "Set element value", mutating: true, keyArgs: ["file", "formId", "path", "value"] },
        { name: "elements.add_child", summary: "Add child element", mutating: true },
        { name: "elements.remove_child", summary: "Remove child element", mutating: true },
        { name: "elements.copy_child_to", summary: "Copy a child into another record", mutating: true },
      ],
    },
    {
      name: "jobs",
      blurb: "Async work surface; 10 kinds. dryRun defaults true on start.",
      commands: [
        { name: "jobs.start", summary: "Queue a job of one of the 10 kinds", mutating: true, keyArgs: ["kind", "dryRun"] },
        { name: "jobs.get", summary: "Poll job state", mutating: false, keyArgs: ["jobId"] },
        { name: "jobs.findings", summary: "Page findings from a job", mutating: false, keyArgs: ["jobId"] },
        { name: "jobs.cancel", summary: "Request cancel", mutating: false },
        { name: "jobs.discard", summary: "Drop a finished job from history", mutating: false },
      ],
    },
    {
      name: "scripts",
      blurb: "Pascal scripting; Agent/ namespace writable.",
      commands: [
        { name: "scripts.list", summary: "List stored scripts", mutating: false },
        { name: "scripts.read", summary: "Read a script body", mutating: false, keyArgs: ["id"] },
        { name: "scripts.write", summary: "Write to Agent/<id>.pas", mutating: true, keyArgs: ["id", "source"] },
        { name: "scripts.delete", summary: "Delete from Agent/ namespace", mutating: true, keyArgs: ["id"] },
        { name: "scripts.run", summary: "Run a script synchronously", mutating: true, keyArgs: ["id", "targets", "timeoutMs"] },
      ],
    },
  ],
};

export function allDigestCommands(): string[] {
  return CAPABILITIES_DIGEST.groups.flatMap((g) => g.commands.map((c) => c.name));
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/capabilities-digest.test.ts
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/capabilities-digest.ts tools/xedit-mcp/tests/unit/capabilities-digest.test.ts
git commit -m "feat(xedit-mcp): curated 47-command capabilities digest"
```

---

### Task 13: `xedit_session` tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/session.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-session.test.ts`

**Rationale:** Special-case tool that builds the `ToolContext` and returns a session summary. Does not flow through `runTool` because it is the bootstrap that *produces* the context other tools consume.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-session.test.ts
import { describe, it, expect } from "vitest";
import { xeditSessionTool } from "../../src/tools/session.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("xedit_session tool", () => {
  it("returns an ok envelope with describe + capability summary", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({
        contractVersion: "0.10", commands: ["records.get"], supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "MyPatch.esp"] }),
      "session.get_dirty_state": () => ({ dirtyFiles: [], unsavedChangeCount: 0, dirty: false }),
    });
    const { tool, getContext } = xeditSessionTool({ adapter, sessionId: "s-test" });
    const env = await tool({});
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      gameMode: "Fallout4",
      contractVersion: "0.10",
      loadOrderSize: 2,
      consentEnabled: true,
      dirty: false,
    });
    const ctx = getContext();
    expect(ctx?.loadOrder).toContain("MyPatch.esp");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-session.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/session.ts`**

```ts
// src/tools/session.ts
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { buildContext } from "../session.js";

export interface XeditSessionToolOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export interface XeditSessionTool {
  /** The MCP tool handler. */
  tool: (args: Record<string, unknown>) => Promise<Envelope>;
  /** Access the most recently built ToolContext (for other tools to share). */
  getContext: () => ToolContext | undefined;
}

export function xeditSessionTool(opts: XeditSessionToolOptions): XeditSessionTool {
  let ctx: ToolContext | undefined;
  return {
    tool: async (_args: Record<string, unknown>): Promise<Envelope> => {
      try {
        ctx = await buildContext(opts);
        const dirtyRes = await opts.adapter.call({ command: "session.get_dirty_state", args: {} });
        const dirty = dirtyRes.ok ? (dirtyRes.result as { dirty?: boolean; dirtyFiles?: string[]; unsavedChangeCount?: number }) : {};
        return okEnv({
          tool: "xedit_session",
          summary: `daemon ready (${ctx.capabilities?.gameMode ?? "?"}, ${ctx.loadOrder?.length ?? 0} files)`,
          status: "completed",
          data: {
            gameMode: ctx.capabilities?.gameMode,
            contractVersion: ctx.capabilities?.contractVersion,
            loadOrderSize: ctx.loadOrder?.length ?? 0,
            consentEnabled: !!ctx.consentEnabled,
            mcpModeActive: !!ctx.mcpModeActive,
            dirty: dirty.dirty === true,
          },
          dirty: { files: dirty.dirtyFiles ?? [], unsavedChangeCount: dirty.unsavedChangeCount ?? 0 },
        });
      } catch (err) {
        return refuse({
          tool: "xedit_session",
          summary: "Failed to build session context",
          code: MCP_ERROR_CODES.STATE_VIOLATION,
          hint: (err as Error).message,
        });
      }
    },
    getContext: () => ctx,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-session.test.ts
```

Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/session.ts tools/xedit-mcp/tests/unit/tool-session.test.ts
git commit -m "feat(xedit-mcp): xedit_session tool (bootstrap + ToolContext)"
```

---

### Task 14: `xedit_list_capabilities` tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/list-capabilities.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-list-capabilities.test.ts`

**Rationale:** Returns the curated digest with a drift report against the live `system.capabilities`. Agent gets the toolbox map without re-paging the contract every session, and learns immediately if the live daemon's command set diverges from what the digest documents.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-list-capabilities.test.ts
import { describe, it, expect } from "vitest";
import { xeditListCapabilitiesTool } from "../../src/tools/list-capabilities.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  capabilities: {
    contractVersion: "0.10",
    gameMode: "Fallout4",
    commands: ["system.describe", "records.get", "records.brand_new_thing"],
    fetchedAt: "now",
  },
};

describe("xedit_list_capabilities tool", () => {
  it("returns the curated digest + drift report against live commands", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => ctx });
    const env = await tool({});
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as {
      contractVersion: string;
      groups: unknown[];
      drift: { onlyInDigest: string[]; onlyInLive: string[] };
    };
    expect(data.contractVersion).toBe("0.10");
    expect(data.groups.length).toBeGreaterThan(0);
    expect(data.drift.onlyInLive).toContain("records.brand_new_thing");
    expect(data.drift.onlyInDigest.length).toBeGreaterThan(0);
  });

  it("refuses if session context not yet built", async () => {
    const adapter = makeMockAdapter({});
    const tool = xeditListCapabilitiesTool({ adapter, getContext: () => undefined });
    const env = await tool({});
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("state_violation");
    expect(env.hint).toContain("xedit_session");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-list-capabilities.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/list-capabilities.ts`**

```ts
// src/tools/list-capabilities.ts
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { CAPABILITIES_DIGEST, allDigestCommands } from "../capabilities-digest.js";

export interface XeditListCapabilitiesOptions {
  adapter: DaemonAdapter;
  getContext: () => ToolContext | undefined;
}

export function xeditListCapabilitiesTool(
  opts: XeditListCapabilitiesOptions,
): (args: Record<string, unknown>) => Promise<Envelope> {
  return async (_args) => {
    const ctx = opts.getContext();
    if (!ctx?.capabilities) {
      return refuse({
        tool: "xedit_list_capabilities",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    const live = new Set(ctx.capabilities.commands);
    const digest = new Set(allDigestCommands());
    const onlyInLive = [...live].filter((c) => !digest.has(c)).sort();
    const onlyInDigest = [...digest].filter((c) => !live.has(c)).sort();

    return okEnv({
      tool: "xedit_list_capabilities",
      summary: `Digest ${digest.size} commands, live ${live.size}; drift ${onlyInLive.length + onlyInDigest.length}`,
      status: "completed",
      data: {
        contractVersion: ctx.capabilities.contractVersion,
        contractVersionExpected: CAPABILITIES_DIGEST.contractVersionExpected,
        gameMode: ctx.capabilities.gameMode,
        groups: CAPABILITIES_DIGEST.groups,
        drift: { onlyInDigest, onlyInLive },
      },
    });
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-list-capabilities.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/list-capabilities.ts tools/xedit-mcp/tests/unit/tool-list-capabilities.test.ts
git commit -m "feat(xedit-mcp): xedit_list_capabilities tool with drift report"
```

---

### Task 15: `xedit_find_record` tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/find-record.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-find-record.test.ts`

**Rationale:** Locator search across `records.list`, `records.find_by_form_id`, `records.find_by_editor_id`. Shape the response to a slim locator list (no full record dump) — token economy is the point.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-find-record.test.ts
import { describe, it, expect } from "vitest";
import { findRecordSpec, makeFindRecordHandler } from "../../src/tools/find-record.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s", daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_find_record tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-find-")) });

  it("by formId returns a slim locator", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_form_id": (args) => ({
        file: args.file, formId: args.formId, signature: "WEAP", editorId: "Foo",
      }),
    });
    const handler = makeFindRecordHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      locators: [{ file: "Patch.esp", formId: "0x012345", signature: "WEAP", editorId: "Foo" }],
    });
  });

  it("LOAD001 fires when file not in load order", async () => {
    const adapter = makeMockAdapter({ "records.find_by_form_id": () => ({}) });
    const handler = makeFindRecordHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("by editorId across all loaded files", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_editor_id": () => ({
        matches: [{ file: "Patch.esp", formId: "0x0123", signature: "WEAP", editorId: "Foo" }],
      }),
    });
    const handler = makeFindRecordHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ editorId: "Foo" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { locators: unknown[] }).locators).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-find-record.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/find-record.ts`**

```ts
// src/tools/find-record.ts
import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { runTool, type ToolSpec } from "../pipeline/compose.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

const ByFormId = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^0x[0-9a-fA-F]{1,8}$/),
});
const ByEditorId = z.object({
  editorId: z.string().min(1),
  signature: z.string().optional(),
});

export const findRecordSpec: ToolSpec = {
  name: "xedit_find_record",
  // schema is delegated to per-mode dispatch in handler; this is a passthrough placeholder
  schema: z.union([ByFormId, ByEditorId]),
  needs: { daemon: true },
  command: "records.find_by_form_id", // overridden per-call
  summary: (a) => (a.formId ? `find ${String(a.formId)} in ${String(a.file)}` : `find editor ${String(a.editorId)}`),
};

export interface FindRecordOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeFindRecordHandler(opts: FindRecordOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_find_record",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    if (typeof args.formId === "string" && typeof args.file === "string") {
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_form_id",
          needs: { daemon: true, targetFileFromArg: "file" },
          shape: (result) => ({ locators: [normalizeLocator(result, args)] }),
        },
        { args, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }
    if (typeof args.editorId === "string") {
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_editor_id",
          shape: (result) => {
            const matches = (result as { matches?: unknown[] }).matches ?? [];
            return { locators: matches.map((m) => normalizeLocator(m, args)) };
          },
        },
        { args, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }
    return refuse({
      tool: "xedit_find_record",
      summary: "Provide either {file, formId} or {editorId}",
      code: MCP_ERROR_CODES.INVALID_REQUEST,
      hint: "Pass exactly one search mode.",
    });
  };
}

function normalizeLocator(raw: unknown, args: Record<string, unknown>): Record<string, unknown> {
  const r = (raw ?? {}) as Record<string, unknown>;
  return {
    file: r.file ?? args.file,
    formId: r.formId ?? args.formId,
    signature: r.signature,
    editorId: r.editorId ?? args.editorId,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-find-record.test.ts
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/find-record.ts tools/xedit-mcp/tests/unit/tool-find-record.test.ts
git commit -m "feat(xedit-mcp): xedit_find_record tool (formId + editorId dispatch)"
```

---

### Task 16: `xedit_read_record` tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/read-record.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-read-record.test.ts`

**Rationale:** Composite read: a single call returns record summary + winning override + base record + conflict status. This is the highest-frequency W2 operation and the token-economy difference (one shaped envelope vs four raw daemon responses) is significant.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-read-record.test.ts
import { describe, it, expect } from "vitest";
import { makeReadRecordHandler } from "../../src/tools/read-record.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s", daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_read_record tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-read-")) });

  it("returns composite read on the happy path", async () => {
    const adapter = makeMockAdapter({
      "records.get": () => ({ formId: "0x012345", signature: "WEAP", editorId: "Foo", fields: { FULL: "Foo Name" } }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.base_record": () => ({ file: "Fallout4.esm", formId: "0x000045" }),
      "records.conflict_status": () => ({ status: "ITPO", details: "identical to previous override" }),
    });
    const handler = makeReadRecordHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      record: { editorId: "Foo" },
      winningOverride: { file: "Patch.esp" },
      baseRecord: { file: "Fallout4.esm" },
      conflict: { status: "ITPO" },
    });
  });

  it("LOAD001 fires when file not loaded", async () => {
    const adapter = makeMockAdapter({});
    const handler = makeReadRecordHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-read-record.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/read-record.ts`**

```ts
// src/tools/read-record.ts
import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";

const Args = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^0x[0-9a-fA-F]{1,8}$/),
});

export interface ReadRecordOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeReadRecordHandler(opts: ReadRecordOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_read_record",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    const v = validateArgs(Args, args, { tool: "xedit_read_record" });
    if (v) { await audit(opts, "xedit_read_record", args, v); return v; }
    const p = precheck({ tool: "xedit_read_record", args }, { ctx, needs: { daemon: true, targetFileFromArg: "file" } });
    if (p) { await audit(opts, "xedit_read_record", args, p); return p; }
    const r = await runRules({ tool: "xedit_read_record", args, ctx, registry: opts.registry });
    if (r) { await audit(opts, "xedit_read_record", args, r); return r; }

    const [rec, win, base, conflict] = await Promise.all([
      opts.adapter.call({ command: "records.get", args }),
      opts.adapter.call({ command: "records.winning_override", args }),
      opts.adapter.call({ command: "records.base_record", args }),
      opts.adapter.call({ command: "records.conflict_status", args }),
    ]);

    if (!rec.ok) {
      const env = refuse({
        tool: "xedit_read_record",
        summary: `records.get failed: ${rec.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: rec.error.message,
        detail: { daemonCode: rec.error.code },
      });
      await audit(opts, "xedit_read_record", args, env);
      return env;
    }

    const env = okEnv({
      tool: "xedit_read_record",
      summary: `read ${String(args.formId)} in ${String(args.file)}`,
      status: "completed",
      data: {
        record: rec.result,
        winningOverride: win.ok ? win.result : null,
        baseRecord: base.ok ? base.result : null,
        conflict: conflict.ok ? conflict.result : null,
      },
    });
    await audit(opts, "xedit_read_record", args, env);
    return env;
  };
}

async function audit(opts: ReadRecordOptions, tool: string, args: Record<string, unknown>, env: Envelope) {
  await opts.audit.append({
    tool, argsHash: simpleHash(args), decision: env.ok ? "ok" : "refused", ok: env.ok,
    code: env.ok ? undefined : env.code,
  });
}

function simpleHash(args: Record<string, unknown>): string {
  let h = 0;
  const s = JSON.stringify(args);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h).toString(16);
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-read-record.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/read-record.ts tools/xedit-mcp/tests/unit/tool-read-record.test.ts
git commit -m "feat(xedit-mcp): xedit_read_record tool (composite: record + winning + base + conflict)"
```

---

### Task 17: `xedit_inspect_conflicts` tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/inspect-conflicts.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-inspect-conflicts.test.ts`

**Rationale:** The W2 audit headline tool: given a record, return conflict status + override chain (`records.winning_override` + traversal of references-in via `records.referenced_by`) shaped to a small summary. Returns a verdict label (`no_conflict | itpo | itm | breaking`) so skills/agents can branch on it.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-inspect-conflicts.test.ts
import { describe, it, expect } from "vitest";
import { makeInspectConflictsHandler } from "../../src/tools/inspect-conflicts.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s", daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp", "Other.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_inspect_conflicts tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-conflict-")) });

  it("verdict=no_conflict when only one override exists", async () => {
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({ status: "no_conflict" }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [] }),
    });
    const handler = makeInspectConflictsHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { verdict: string }).verdict).toBe("no_conflict");
  });

  it("verdict=breaking when conflict_status reports a hard conflict label", async () => {
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({ status: "conflict_critical" }),
      "records.winning_override": () => ({ file: "Other.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [{ file: "Mod.esp", formId: "0x55" }] }),
    });
    const handler = makeInspectConflictsHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { verdict: string }).verdict).toBe("breaking");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-inspect-conflicts.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/inspect-conflicts.ts`**

```ts
// src/tools/inspect-conflicts.ts
import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";

const Args = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^0x[0-9a-fA-F]{1,8}$/),
});

export type Verdict = "no_conflict" | "itpo" | "itm" | "minor" | "breaking";

export interface InspectConflictsOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeInspectConflictsHandler(opts: InspectConflictsOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_inspect_conflicts",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    const v = validateArgs(Args, args, { tool: "xedit_inspect_conflicts" });
    if (v) return v;
    const p = precheck({ tool: "xedit_inspect_conflicts", args }, { ctx, needs: { daemon: true, targetFileFromArg: "file" } });
    if (p) return p;
    const r = await runRules({ tool: "xedit_inspect_conflicts", args, ctx, registry: opts.registry });
    if (r) return r;

    const [conflict, winning, referencedBy] = await Promise.all([
      opts.adapter.call({ command: "records.conflict_status", args }),
      opts.adapter.call({ command: "records.winning_override", args }),
      opts.adapter.call({ command: "records.referenced_by", args }),
    ]);

    if (!conflict.ok) {
      return refuse({
        tool: "xedit_inspect_conflicts",
        summary: `records.conflict_status failed: ${conflict.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: conflict.error.message,
      });
    }

    const status = String((conflict.result as { status?: string }).status ?? "unknown");
    const verdict: Verdict = mapVerdict(status);

    return okEnv({
      tool: "xedit_inspect_conflicts",
      summary: `verdict ${verdict} for ${String(args.formId)}`,
      status: "completed",
      data: {
        verdict,
        rawStatus: status,
        winningOverride: winning.ok ? winning.result : null,
        referencedBy: referencedBy.ok ? referencedBy.result : null,
      },
    });
  };
}

function mapVerdict(status: string): Verdict {
  const s = status.toLowerCase();
  if (s.includes("itpo")) return "itpo";
  if (s.includes("itm")) return "itm";
  if (s === "no_conflict" || s === "no conflict") return "no_conflict";
  if (s.includes("critical") || s.includes("breaking")) return "breaking";
  if (s.includes("conflict")) return "minor";
  return "minor";
}
```

> The exact status strings produced by `records.conflict_status` need to be confirmed against the live daemon in Task 23. If the verdict mapping does not align, update `mapVerdict()` and re-test. The mapping is intentionally lenient (defaults to `"minor"`) so unknown statuses do not become silent `"no_conflict"`.

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-inspect-conflicts.test.ts
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/inspect-conflicts.ts tools/xedit-mcp/tests/unit/tool-inspect-conflicts.test.ts
git commit -m "feat(xedit-mcp): xedit_inspect_conflicts tool with verdict label"
```

---

### Task 18: `xedit_call` atomic passthrough tool

**Files:**
- Create: `tools/xedit-mcp/src/tools/call.ts`
- Create: `tools/xedit-mcp/tests/unit/tool-call.test.ts`

**Rationale:** The escape valve for novel/debugging/free-composition scenarios (spec §5 Layer B, §10 dispatch). Accepts any native command name; validates it against the capabilities digest; runs the same pipeline (stage [3] sees `xedit_call` and the underlying command name both, when rules opt-in). Closes the "agent drops to direct CLI" hole because there is no longer a reason to.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/tool-call.test.ts
import { describe, it, expect } from "vitest";
import { makeCallHandler } from "../../src/tools/call.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s", daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_call atomic passthrough", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-call-")) });

  it("forwards a known command and returns the daemon result", async () => {
    const adapter = makeMockAdapter({
      "records.get": (a) => ({ formId: a.formId, fields: { FULL: "Hi" } }),
    });
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "records.get", args: { file: "Patch.esp", formId: "0x012345" } });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { fields: Record<string, string> }).fields.FULL).toBe("Hi");
  });

  it("refuses unknown command with hint pointing to capabilities digest", async () => {
    const adapter = makeMockAdapter({});
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "no.such.command", args: {} });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
    expect(env.hint).toContain("xedit_list_capabilities");
  });

  it("LOAD001 still fires against args.file even via passthrough", async () => {
    const adapter = makeMockAdapter({ "records.get": () => ({}) });
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "records.get", args: { file: "Ghost.esp", formId: "0x012345" } });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/tool-call.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/tools/call.ts`**

```ts
// src/tools/call.ts
import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { forwardCall } from "../pipeline/forward.js";
import { allDigestCommands } from "../capabilities-digest.js";

const CallArgs = z.object({
  command: z.string().min(1),
  args: z.record(z.unknown()).optional(),
});

export interface CallOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeCallHandler(opts: CallOptions) {
  const knownCommands = new Set(allDigestCommands());
  return async (rawArgs: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_call",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    const v = validateArgs(CallArgs, rawArgs, { tool: "xedit_call" });
    if (v) { await opts.audit.append({ tool: "xedit_call", argsHash: "v-fail", decision: "refused", ok: false, code: v.code }); return v; }

    const { command, args = {} } = rawArgs as { command: string; args?: Record<string, unknown> };

    // Allow live-daemon commands that exist in capabilities but not yet in the digest,
    // but warn. Reject only if both the digest AND live capabilities lack the command.
    const liveCommands = new Set(ctx.capabilities?.commands ?? []);
    const knownToDigest = knownCommands.has(command);
    const knownToLive = liveCommands.has(command);
    if (!knownToDigest && !knownToLive) {
      const env = refuse({
        tool: "xedit_call",
        summary: `Unknown command: ${command}`,
        code: MCP_ERROR_CODES.INVALID_REQUEST,
        hint: "Check xedit_list_capabilities for the supported command set.",
        detail: { command },
      });
      await opts.audit.append({ tool: "xedit_call", argsHash: "unknown", decision: "refused", ok: false, code: env.code });
      return env;
    }

    const p = precheck({ tool: "xedit_call", args }, { ctx, needs: { daemon: true, targetFileFromArg: typeof args.file === "string" ? "file" : undefined } });
    if (p) { await opts.audit.append({ tool: "xedit_call", argsHash: "p-fail", decision: "refused", ok: false, code: p.code }); return p; }

    // Rules opt-in by listing either "xedit_call" or the native command name in appliesTo.
    // For Batch 1, only LOAD001 applies; it already lists "xedit_call".
    const r = await runRules({ tool: "xedit_call", args, ctx, registry: opts.registry });
    if (r) { await opts.audit.append({ tool: "xedit_call", argsHash: "r-fail", decision: "refused", ok: false, code: r.code, ruleHits: [r.code.replace(/^rule_/, "")] }); return r; }

    const env = await forwardCall({
      tool: "xedit_call",
      command,
      args,
      adapter: opts.adapter,
      summary: `passthrough ${command}`,
    });
    if (env.ok && !knownToDigest) {
      env.warnings.push({
        code: "DIGEST_DRIFT",
        message: `Command ${command} present in live daemon but missing from curated digest. Consider updating capabilities-digest.ts.`,
        severity: "MEDIUM",
      });
    }
    await opts.audit.append({ tool: "xedit_call", argsHash: "ok", decision: env.ok ? "ok" : "refused", ok: env.ok, code: env.ok ? undefined : env.code });
    return env;
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/tool-call.test.ts
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/tools/call.ts tools/xedit-mcp/tests/unit/tool-call.test.ts
git commit -m "feat(xedit-mcp): xedit_call atomic passthrough (closes CLI-bypass hole)"
```

---

## Phase E — MCP Server Entry

### Task 19: Wire all tools into the MCP server (`src/index.ts`)

**Files:**
- Replace: `tools/xedit-mcp/src/index.ts` (previously a stub)
- Create: `tools/xedit-mcp/tests/unit/server.test.ts`

**Rationale:** Register the 6 Batch-1 tools (`xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`, `xedit_call`) with `@modelcontextprotocol/sdk`'s `Server`. Single shared `ToolContext` accessor lets later tools see what `xedit_session` produced. Production transport is stdio; tests exercise the tool handlers directly.

- [ ] **Step 1: Write the failing test**

```ts
// tests/unit/server.test.ts
import { describe, it, expect } from "vitest";
import { buildServerToolset } from "../../src/index.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("MCP server toolset", () => {
  it("registers exactly the Batch 1 tools and dispatches them", async () => {
    const adapter = makeMockAdapter({
      "system.describe": () => ({ gameMode: "Fallout4", dataPath: "C:/x" }),
      "system.capabilities": () => ({
        contractVersion: "0.10", commands: ["records.get"], supports: { iKnowWhatImDoing: true },
      }),
      "files.list": () => ({ files: ["Fallout4.esm", "Patch.esp"] }),
      "session.get_dirty_state": () => ({ dirty: false, dirtyFiles: [], unsavedChangeCount: 0 }),
      "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.base_record": () => ({ file: "Fallout4.esm" }),
      "records.conflict_status": () => ({ status: "no_conflict" }),
      "records.referenced_by": () => ({ referencers: [] }),
    });
    const ts = buildServerToolset({ adapter, sessionId: "test", auditDir: undefined });
    expect(ts.list().sort()).toEqual([
      "xedit_call",
      "xedit_find_record",
      "xedit_inspect_conflicts",
      "xedit_list_capabilities",
      "xedit_read_record",
      "xedit_session",
    ]);

    const sessionEnv = await ts.invoke("xedit_session", {});
    expect(sessionEnv.ok).toBe(true);

    const readEnv = await ts.invoke("xedit_read_record", { file: "Patch.esp", formId: "0x012345" });
    expect(readEnv.ok).toBe(true);
  });

  it("returns a structured refusal for an unknown tool name", async () => {
    const adapter = makeMockAdapter({});
    const ts = buildServerToolset({ adapter, sessionId: "test", auditDir: undefined });
    const env = await ts.invoke("xedit_nope", {});
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- tests/unit/server.test.ts
```

Expected: FAIL — `buildServerToolset` not exported.

- [ ] **Step 3: Replace `src/index.ts`**

```ts
// src/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { tmpdir } from "node:os";
import { join } from "node:path";

import type { DaemonAdapter } from "./daemon-adapter.js";
import type { Envelope } from "./types.js";
import { createAuditLogger } from "./audit.js";
import { defaultRegistry } from "./rules/registry.js";
import { xeditSessionTool } from "./tools/session.js";
import { xeditListCapabilitiesTool } from "./tools/list-capabilities.js";
import { makeFindRecordHandler } from "./tools/find-record.js";
import { makeReadRecordHandler } from "./tools/read-record.js";
import { makeInspectConflictsHandler } from "./tools/inspect-conflicts.js";
import { makeCallHandler } from "./tools/call.js";
import { refuse } from "./envelope.js";
import { MCP_ERROR_CODES } from "./types.js";

export interface ServerToolsetOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  auditDir?: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export interface ServerToolset {
  list: () => string[];
  invoke: (name: string, args: Record<string, unknown>) => Promise<Envelope>;
}

export function buildServerToolset(opts: ServerToolsetOptions): ServerToolset {
  const audit = createAuditLogger({
    baseDir: opts.auditDir ?? join(tmpdir(), "xedit-mcp-audit"),
  });
  const registry = defaultRegistry();
  const session = xeditSessionTool({
    adapter: opts.adapter,
    sessionId: opts.sessionId,
    daemonPid: opts.daemonPid,
    mcpModeActive: opts.mcpModeActive,
  });
  const getCtx = session.getContext;

  const listCaps = xeditListCapabilitiesTool({ adapter: opts.adapter, getContext: getCtx });
  const find = makeFindRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const read = makeReadRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const inspect = makeInspectConflictsHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const call = makeCallHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });

  const handlers: Record<string, (a: Record<string, unknown>) => Promise<Envelope>> = {
    xedit_session: session.tool,
    xedit_list_capabilities: listCaps,
    xedit_find_record: find,
    xedit_read_record: read,
    xedit_inspect_conflicts: inspect,
    xedit_call: call,
  };

  return {
    list: () => Object.keys(handlers),
    invoke: async (name, args) => {
      const h = handlers[name];
      if (!h) {
        return refuse({
          tool: name,
          summary: `Unknown tool: ${name}`,
          code: MCP_ERROR_CODES.INVALID_REQUEST,
          hint: "List available tools via the MCP listTools request.",
        });
      }
      return h(args);
    },
  };
}

// Production entry: stdio MCP server. The MCP SDK request/response wiring keeps
// the same envelope shape so consumers see a uniform { ok, ... } structure.
export async function main(): Promise<void> {
  // adapter is left undefined here for the production binary; an integration harness
  // is expected to construct a real PowerShell adapter and call buildServerToolset.
  // The stub main() is provided so `node dist/index.js` does not crash; real usage
  // is via an init script that wires the adapter (see README).
  const server = new Server(
    { name: "xedit-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      { name: "xedit_session", description: "Ensure daemon, return session summary." },
      { name: "xedit_list_capabilities", description: "Curated digest + live drift report." },
      { name: "xedit_find_record", description: "Locate records by formId or editorId." },
      { name: "xedit_read_record", description: "Composite read (record + winning + base + conflict)." },
      { name: "xedit_inspect_conflicts", description: "Conflict audit verdict + winning + referencedBy." },
      { name: "xedit_call", description: "Atomic passthrough for any native daemon command (still in harness)." },
    ].map((t) => ({ ...t, inputSchema: { type: "object" } })),
  }));
  server.setRequestHandler(CallToolRequestSchema, async () => ({
    content: [{ type: "text", text: JSON.stringify({ ok: false, code: "not_wired", hint: "Production entry requires adapter wiring; use buildServerToolset()." }) }],
    isError: true,
  }));
  await server.connect(new StdioServerTransport());
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
```

> The production stdio entry is intentionally minimal in Batch 1: real usage goes through `buildServerToolset()` with a wired PowerShell adapter, which the Phase G integration test exercises. Wiring the adapter into `main()` is split into a follow-up because the launch flow (mo2-vfs-launcher → ensure-daemon → resolve PID → connect adapter) is the same surface the integration test will define; we do it once, there.

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- tests/unit/server.test.ts
npm run typecheck
npm run build
```

Expected: server tests PASS (2 tests), typecheck PASS, build PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/xedit-mcp/src/index.ts tools/xedit-mcp/tests/unit/server.test.ts
git commit -m "feat(xedit-mcp): wire Batch 1 toolset into MCP server entry"
```

---

## Phase F — Skills

These are markdown artifacts. "Test" here means a structural checklist (required sections present, all referenced commands appear in the digest, links resolve). Apply the same discipline: draft → verify → commit.

### Task 20: Hub skill `xedit-automation/SKILL.md`

**Files:**
- Create: `.opencode/skills/xedit-automation/SKILL.md`

**Rationale:** The always-load entry point. Carries the Top-N gotchas digest, the CLI/MCP/sub-agent dispatch table, anti-pattern bans, confidence + dry-run discipline, role-agnostic delegation recipes, and the self-growing-KB pointer (spec §9). Format: global Superpowers YAML frontmatter.

- [ ] **Step 1: Create the file**

```markdown
---
name: xedit-automation
description: Use whenever the task involves inspecting, modifying, or building plugins for Bethesda games via the forked xEdit automation daemon. Loads first; routes to the right path (MCP intent tool, MCP atomic passthrough, or sub-agent delegation) and prevents the agent from bypassing the harness.
---

# xEdit Automation — Hub Skill

This skill is the always-loaded entry point for any xEdit work. It is the single source of truth for "which path do I use" and "what must I never do." Specialised task skills (e.g. `xedit-conflict-audit`) inherit its routing, anti-patterns, and verification discipline; they do not restate them.

## Toolbox at a glance (capability digest, Top-N)

The forked xEdit daemon exposes 47 commands across 7 groups, all reachable through the MCP. The most common ones:

- **Discovery & session** — `xedit_session`, `xedit_list_capabilities`. Call `xedit_session` first every conversation. Then call `xedit_list_capabilities` once to see the toolbox and check for drift between the curated digest and the live daemon.
- **Reading records & conflicts** — `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`. These are the W2 (conflict audit) backbone.
- **Atomic passthrough** — `xedit_call(command, args)`. For any native daemon command that does not have an intent tool yet. Still runs the full pipeline (validation → state → rules → audit). Use it whenever the intent tools do not fit.

For the deep reference (all 47 commands, error codes, save semantics, locator format, UESP CK wiki, glossary), see the companion file `xedit-knowledgebase.md` in this skill directory.

## Routing doctrine (which path to use)

| Task shape | Path |
|---|---|
| High-frequency known intent (audit a conflict, read a record, run a job, write a patch) | **MCP intent tool** |
| Novel / debugging / free composition of native commands | **MCP atomic passthrough**: `xedit_call(command, args)` — still in harness |
| Exploratory atomic-op storm (trial-and-error, repeated read-eval, hypothesis testing) | **Delegate to a read-only investigator sub-agent** with this skill loaded; the sub-agent burns its own context, returns a distilled summary |
| Large formalisable bulk mutation | **MCP `xedit_run_script`** (Batch 4+) with dry-run + snapshot |
| Daemon explicitly in default (non-MCP) mode, manual debug only | Direct `xedit-client.ps1` is acceptable — but ONLY when the user has explicitly accepted the risk and the daemon is not in `-automation-mcp-mode` |

**The agent should never have a reason to bypass the MCP.** Atomic passthrough exists for that.

## Anti-patterns (hard bans)

Never do any of the following. Each ban is encoded as an MCP rule or daemon-side refusal, but the skill states them so the agent does not even attempt:

1. **Do not write Python (or any other language) to parse `.esp/.esm/.esl` files directly.** The daemon is the only correct path. If you find yourself reaching for a binary plugin parser, stop and use `xedit_call` instead.
2. **Do not trust an `ok: true` response as durability.** A save with `pendingShutdown > 0` is deferred; durability requires a daemon restart and readback (see §10 of the design spec).
3. **Do not call mutating ops in mcp-mode without going through the MCP.** Direct pipe writes will be refused by the daemon with `mcp_mode_required`.
4. **Do not page `system.capabilities` every session.** The digest in `xedit_list_capabilities` already carries the curated map; only call live capabilities once to check drift.
5. **Do not delete or mark-deleted a record that is referenced by other plugins** without first calling `xedit_call records.referenced_by` and accepting the consequences. Snapshot does not cleanly recover deletions.

## Confidence + dry-run discipline (borrowed from skyrimvr-claude-toolkit)

Before any mutating action:

1. State your confidence (0-100%) and your top 3 assumptions.
2. If confidence < 90%, investigate first (read records, inspect conflicts, list references) until ≥ 90%.
3. For HIGH-RISK mutations, the MCP will return a preview envelope with `confirmToken`. Read the preview, decide, then commit with the token. Treat the preview as the contract.

## Sub-agent delegation recipes (role-agnostic)

When delegating, do not hard-code role names — the harness will map them. Use these recipes:

**Read-only investigator** — for exploratory storms, conflict surveys, and "what's in this plugin" reconnaissance:

> Dispatch a read-only investigator sub-agent with this skill loaded. Provide the question, the target files, and the budget (token / time / step count). The sub-agent should return a distilled summary (verdict + key evidence + open questions), not the raw daemon round-trips.

**Bounded mutation worker** — for well-defined batch edits (Batch 4+):

> Dispatch a bounded-execution sub-agent with this skill and the patch-authoring skill loaded. Provide the spec, the snapshot expectations, and the acceptance checks. The sub-agent should perform the mutations through the MCP and return the snapshot IDs + readback proof.

## Self-growing knowledgebase

After any session that produced a footgun (an unexpected refusal, a non-obvious recovery, a surprising daemon behavior):

1. Append a short note to `xedit-knowledgebase.md` under "Lessons" — file/record/element involved, what went wrong, what worked.
2. If the footgun is mechanically detectable, draft a rule at `tools/xedit-mcp/src/rules/candidates/<id>.ts` describing the check and the corrective hint. Candidates require human review before promotion.

## When this skill applies

- Any task involving Bethesda plugin files (`.esp/.esm/.esl`) for FO4, Skyrim, FO76, Starfield in this repo's MO2 harness.
- Any conflict / patching / cleaning / ESL / scripting task against xEdit.
- Whenever the task description names xEdit, plugin records, FormIDs, masters, conflicts, ITM/UDR, ESL flagging, or Pascal Edit Scripts.

When in doubt, load it.
```

- [ ] **Step 2: Verify the file's structure**

```bash
grep -E "^(##|---|name:|description:)" .opencode/skills/xedit-automation/SKILL.md | head -30
```

Expected output contains, in order: `---`, `name: xedit-automation`, `description: ...`, `---`, `## Toolbox at a glance ...`, `## Routing doctrine ...`, `## Anti-patterns ...`, `## Confidence ...`, `## Sub-agent delegation recipes ...`, `## Self-growing knowledgebase`, `## When this skill applies`.

- [ ] **Step 3: Commit**

```bash
git add .opencode/skills/xedit-automation/SKILL.md
git commit -m "docs(skills): xedit-automation hub skill"
```

---

### Task 21: Knowledgebase `xedit-knowledgebase.md`

**Files:**
- Create: `.opencode/skills/xedit-automation/xedit-knowledgebase.md`

**Rationale:** The two-tier knowledge pattern from skyrimvr-claude-toolkit. Hub keeps the Top-N; KB is the deep reference (47-command digest in prose, error codes, save semantics, locators, UESP CK wiki pointer, glossary, known drift). Spec §9.

- [ ] **Step 1: Create the file**

````markdown
# xEdit Automation — Knowledgebase

This is the deep reference. Consult it when the hub skill's Top-N is not enough. When you discover a new gotcha, append to "Lessons" at the bottom.

## External references (consult first)

- **UESP Creation Kit Wiki** — https://ck.uesp.net/wiki — primary source for record schema, field meanings, signature reference (KYWD, WEAP, ARMA, NPC_, MISC, etc.), and engine semantics. When you ask "what does this field actually mean," go here before guessing.
- Forked xEdit contract docs (local mirror): `D:\TES5Edit-contrib\docs\notes\automation-contract\` — wire protocol, examples, COMPATIBILITY notes.
- Design spec: `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`.

## Daemon protocol essentials

- Transport: Windows named pipe `\\.\pipe\xedit-<PID>`. One connection = one request → one response.
- Request envelope: `{ command, args: {...}, requestId?, id?, mcpToken? }`. `args` is always an object.
- Success envelope: `{ ok: true, command, requestId, result: {...} }`.
- Failure envelope: `{ ok: false, command, requestId, error: { code, message, details? } }`. **Branch on `error.code` only**, never on prose message.
- Contract version drift: source emits `"0.10"`, docs say `"0.9"`. Branch on field presence, not version string. The MCP digest expects `"0.10"`.

## All 47 commands (grouped)

### system.* — always available, no load required
- `system.ping` `{}` → liveness.
- `system.describe` `{}` → app/game-mode/data-path/sub-mode.
- `system.capabilities` `{}` → full live command list and `supports.*` tree. Compare against the digest via `xedit_list_capabilities` once per session.

### session.*
- `session.get_dirty_state` → which files have unsaved changes (`dirty: bool`, `dirtyFiles: []`, `unsavedChangeCount: int`).
- `session.get_gui_snapshot` → coarse modal-blocker probe; `hasBlockers: bool`.
- `session.save` `{ files: [...] }` → **mutating**, gated by `-IKnowWhatImDoing`. Response carries `savedFilesNow`, `savedFilesPendingShutdown`. Pending-shutdown saves are NOT durable until daemon restart and readback.
- `session.navigate_to_record` `{ file, formId, path? }` → drive the GUI JumpTo seam.

### files.*
- `files.list`, `files.get` — read.
- `files.create` `{ name, extension: ".esp"|".esm"|".esl", flags?: ["esm","esl"], template?: "empty" }` — mutating.
- `files.add_required_masters` `{ file, masters: [...] }` — mutating.
- `files.get_header`, `files.get_masters` — read.
- `files.set_header_flags`, `files.sort_masters`, `files.clean_masters` — mutating. Persistence still needs explicit `session.save`.

### records.* (15)
Read/search: `records.list`, `records.apply_filter`, `records.base_record`, `records.find_by_form_id`, `records.find_by_editor_id`, `records.get`, `records.master_or_self`, `records.winning_override`, `records.conflict_status`, `records.references`, `records.referenced_by`.
Mutating: `records.create` (signature support is dynamic — read `system.capabilities`), `records.copy_into`, `records.delete`, `records.mark_deleted`.

Locator shape (used throughout): `{ file: "Fallout4.esm", formId: "0x0000003C", path: "" }`. Root locators use `path: ""`; nested element addressing extends with strings like `"[0]"`. FormIDs are load-order-resolved.

### elements.* (8)
Read: `elements.get`, `elements.children`, `elements.conflict_status`, `elements.required_masters`.
Mutating: `elements.set_value`, `elements.add_child`, `elements.remove_child`, `elements.copy_child_to`.

### jobs.* — async work (10 kinds, single-active-job bounded)
Lifecycle: `jobs.start`, `jobs.get`, `jobs.findings`, `jobs.cancel`, `jobs.discard`.
States: `queued | running | succeeded | failed | cancel_requested | canceled`.
Apply mode requires explicit `dryRun: false`; omitted `dryRun` defaults to `true` (non-mutating).

**Frozen kinds list** (order is stable):
1. `files.hygiene.batch`
2. `plugin.esl.analyze`
3. `plugin.esl.apply`
4. `plugin.formids.compact_for_esl`
5. `validation.check_for_errors`
6. `validation.check_for_itm`
7. `validation.check_for_deleted_refs`
8. `cleaning.quick_clean`
9. `cleaning.quick_auto_clean`
10. `cleaning.sort_and_clean_masters`

### scripts.* (5)
- `scripts.list { prefix?, limit? }`, `scripts.read { id }`, `scripts.write { id, source, overwrite? }`, `scripts.delete { id }`. Writable namespace is **only `Agent/`**.
- `scripts.run { id, targets?, timeoutMs?, maxStatements? }` — synchronous on GUI thread, single-process-single-runner, shared with GUI Apply Script via a runner token. Default timeout 30 s, default budget 1,000,000 statements.

## Save & durability semantics

- A `session.save` response with `savedFilesPendingShutdown` is **not** durable. The save is deferred until daemon shutdown.
- Durability proof = (a) save → (b) daemon restart (new PID) → (c) readback of the affected records/headers/masters confirms the intended state.
- Always restart before declaring a mutating workflow complete.

## Error code reference (stable snake_case)

- Transport / validation: `invalid_request`, `unknown_command`, `internal_error`, `unknown_job_kind`, `consent_required`, `file_not_found`, `record_not_found`, `invalid_target`, `save_failed`.
- Script lifecycle (frozen 7): `script_blocker_lint`, `script_busy`, `script_external_declaration_not_allowed`, `script_compile_error`, `script_timeout`, `script_statement_budget_exceeded`, `script_runtime_error`.
- MCP-layer additions: `mcp_mode_required`, `state_violation`, `daemon_error`, `confirm_required`, `confirm_token_invalid`, `confirm_token_expired`, `snapshot_failed`, `rule_<ID>`.

## Mutation policy

- All mutating commands require the daemon to be launched with `-IKnowWhatImDoing`.
- `records.create` signature support is dynamic; the legacy `KYWD/MISC` whitelist has been removed in the fork. Always check `system.capabilities` for current allowed signatures.
- Pascal scripts run in a constrained runtime: `runtimeFsRead: true`, `runtimeFsWrite: false`, no UI / shell / clipboard / process-spawn. External declarations are denied.

## Known drift (do not be surprised by these)

- `D:\TES5Edit-contrib\README.md` still references `-AutomationPipe:<pipe-name>`. **That switch does not exist.** The real switches are `-automation-serve`, `-automation-cli-request/response`, `-automation-call-pid`, plus the new `-automation-mcp-mode` (when the fork patch lands).
- Contract version: source `"0.10"`, docs `"0.9"`. Treat as equivalent except for the `consent_required` code and `iKnowWhatImDoing` capability flag, which only exist in 0.10.
- Some daemon responses include emoji or formatted strings; the MCP envelope strips/normalises these. Trust `data` / `summary`; ignore prose flourishes.

## Glossary

- **ITM** — Identical To Master: an override record whose every field matches its master. Safe to remove (cleaning).
- **UDR / "deleted refs"** — Undeleted Reference: a reference flagged as deleted instead of disabled. Cleaning replaces with disable.
- **Master** — A plugin (`.esm` or any plugin tagged with the ESM flag) that other plugins depend on.
- **Override** — A record in plugin B that "shadows" the same FormID from plugin A (its master).
- **Winning override** — The last override in load order; whichever plugin xEdit considers "winning" for that record.
- **Conflict status** — xEdit's coloured-record label: no_conflict, ITM/ITPO, minor, critical, etc.
- **ESL** — Light plugin: limited to 0x800–0xFFF FormID range; shares its 254-slot space with other ESLs.

## Lessons (append as encountered)

> This section is the dogfood log. After any session that surfaced an unexpected behavior, append a short entry: date, summary, what worked, link to the rule candidate if one was drafted.

- (no entries yet)
````

- [ ] **Step 2: Verify the file**

```bash
test -f .opencode/skills/xedit-automation/xedit-knowledgebase.md
grep -c "^## " .opencode/skills/xedit-automation/xedit-knowledgebase.md
grep "https://ck.uesp.net/wiki" .opencode/skills/xedit-automation/xedit-knowledgebase.md
```

Expected: file exists, ≥ 10 `## ` headings, UESP link is present exactly once.

- [ ] **Step 3: Commit**

```bash
git add .opencode/skills/xedit-automation/xedit-knowledgebase.md
git commit -m "docs(skills): xedit-knowledgebase (deep reference, UESP CK wiki, lessons log)"
```

---

### Task 22: Conflict-audit task skill `xedit-conflict-audit/SKILL.md`

**Files:**
- Create: `.opencode/skills/xedit-conflict-audit/SKILL.md`

**Rationale:** Workflow W2's task skill. Inherits hub doctrine; states the audit step sequence, verification, common mistakes, and the read-only sub-agent delegation cue. This is the template all 7 future task skills will copy.

- [ ] **Step 1: Create the file**

```markdown
---
name: xedit-conflict-audit
description: Use when auditing conflicts in a Bethesda plugin set — determining for a record (or a plugin's records) which override wins, what the conflict label is, what references it, and whether the configuration is safe or breaking.
---

# xEdit Conflict Audit (W2)

Inherits the hub `xedit-automation` skill. Do not restate routing or anti-patterns here; this skill is the W2 workflow only.

## Purpose

For a record or a plugin in scope, produce a verdict: `no_conflict | itpo | itm | minor | breaking`, plus the winning override, the override chain, and a list of plugins that reference the record. Output is a concise summary, not the raw daemon round-trips.

## When To Use

- "Why is this mod's change not showing up?" → audit the affected records.
- "Which plugins overlap on this NPC / weapon / armour / keyword?" → audit by editor ID / form ID.
- "Is this load order safe to ship?" → audit a representative sample of records.

## Tools

Use these MCP intent tools (do not drop to `xedit_call` unless an intent tool does not fit):

- `xedit_session` (always first; once per conversation).
- `xedit_list_capabilities` (once per conversation; sanity-check drift).
- `xedit_find_record` (locate the record(s) you want to audit).
- `xedit_inspect_conflicts` (the verdict tool).
- `xedit_read_record` (when you need to see the actual conflicting field values).

If the conflict is broad (many records across many plugins), do not loop through them one by one in the orchestrator — **delegate to a read-only investigator sub-agent** (see Hub skill, "Sub-agent delegation recipes").

## Workflow

1. **Bootstrap session.** `xedit_session({})`. Confirm `gameMode`, `consentEnabled` not needed here (read-only), and `loadOrderSize` matches expectation.
2. **Sanity-check capabilities.** `xedit_list_capabilities({})`. Read the `drift.onlyInLive` and `drift.onlyInDigest` arrays. If a target command you intend to use is missing from live, stop and tell the user.
3. **Scope the audit.** Decide whether the audit is per-record, per-plugin, or per-signature.
4. **Locate records.**
   - Per-record by FormID: `xedit_find_record({ file, formId })`.
   - Per-editor-ID: `xedit_find_record({ editorId })`.
   - Per-plugin: use `xedit_call({ command: "records.list", args: { file } })` for the plugin's record list, then iterate (or delegate to a sub-agent if large).
5. **Inspect conflicts.** For each target: `xedit_inspect_conflicts({ file, formId })`. Read the `verdict` field. Record:
   - `no_conflict` → safe.
   - `itpo` / `itm` → likely safe; consider cleaning.
   - `minor` → human review.
   - `breaking` → halt and surface.
6. **For non-trivial verdicts, read the actual record.** `xedit_read_record({ file, formId })`. Compare `record.fields` vs `winningOverride` vs `baseRecord`. Identify the diverging fields.
7. **Summarise.** Produce a short report: one row per record audited, columns `[file, formId, editorId, verdict, winningFile, referencerCount]`. Surface only the breaking/minor verdicts to the user by default; the rest are appendix.

## Verification (what counts as semantic pass)

- The audit's verdict for each spot-checked record matches what manual xEdit GUI inspection would show.
- For breaking verdicts, you have read the actual record fields and can name the diverging fields.
- The output report is concise: one row per record, no raw daemon envelopes.
- The session's audit log (`.opencode/artifacts/xedit-mcp/audit/YYYY-MM-DD.jsonl`) contains one entry per MCP tool call you made.

If you cannot meet these for a record, mark it `unknown` in the report and explain why — do not guess.

## Common Mistakes

- Calling `xedit_call records.conflict_status` directly when `xedit_inspect_conflicts` would do it with the verdict label already mapped.
- Treating `no_conflict` as proof of safety without reading at least one representative record.
- Looping through hundreds of records in the orchestrator's context. Delegate it.
- Forgetting to call `xedit_session` first; downstream tools will refuse with `state_violation`.
- Asking the daemon for a file that is not in the load order; `LOAD001` will fire — load it via the session first.

## Delegation hints

This workflow is a strong candidate for read-only sub-agent delegation in two cases:

1. **Large scope** (> ~10 records to audit) — the round-trips will fill the orchestrator's context. Delegate the loop; receive the per-record summary table.
2. **Exploratory diagnosis** ("I don't know which record is causing this in-game issue") — let a sub-agent triangulate by editor ID and signature; you'll get the candidates back.

When delegating, include this skill and the hub skill in the sub-agent's prompt and provide the scope + budget.
```

- [ ] **Step 2: Verify the file**

```bash
test -f .opencode/skills/xedit-conflict-audit/SKILL.md
grep -E "^(## |---|name: xedit-conflict-audit)" .opencode/skills/xedit-conflict-audit/SKILL.md | head -20
```

Expected: file exists, frontmatter intact, all required section headings present.

- [ ] **Step 3: Commit**

```bash
git add .opencode/skills/xedit-conflict-audit/SKILL.md
git commit -m "docs(skills): xedit-conflict-audit task skill (W2 workflow)"
```

---

## Phase G — Semantic Verification Against the Live Daemon

### Task 23: End-to-end integration test for W2 conflict audit

**Files:**
- Create: `tools/xedit-mcp/tests/integration/live-conflict-audit.test.ts`
- Create: `tools/xedit-mcp/tests/integration/fixtures.json`
- Create: `tools/xedit-mcp/src/launch.ts` (production wiring: PowerShell adapter, PID resolution, ensure-ready)

**Rationale:** Spec §13 requires that Batch 1 conclude with the W2 conflict audit running end-to-end against the live MO2-backed daemon at `.artifacts/mo2/`, with all envelopes preserved as acceptance artifacts. This task delivers (a) the production wiring (`launch.ts`) that other consumers can also use, and (b) the integration test that exercises the wiring against three representative records of the operator's choice.

- [ ] **Step 1: Create `tools/xedit-mcp/tests/integration/fixtures.json`**

```json
{
  "_help": "Three representative records for W2 acceptance. The user fills in actual entries from their MO2 instance. Each entry: file (in load order), formId (load-order resolved), expectedVerdict.",
  "records": [
    { "file": "Fallout4.esm",        "formId": "0x0000003C", "expectedVerdict": "no_conflict", "note": "control: vanilla record, no overrides expected" },
    { "file": "Fallout4.esm",        "formId": "0x00000000", "expectedVerdict": "no_conflict", "note": "control: TES4 header record" },
    { "file": "OpenCodeTestPlugin.esp", "formId": "0x00000800", "expectedVerdict": "minor",      "note": "test plugin record overriding a vanilla one" }
  ]
}
```

> The user MUST edit `fixtures.json` to reflect three real records from their `.artifacts/mo2/profiles/Default/plugins.txt` before running the test. Until then, the test will report which records were not present and skip the assertion (still producing the run artifact).

- [ ] **Step 2: Implement `tools/xedit-mcp/src/launch.ts`**

```ts
// src/launch.ts
import { spawn } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { setTimeout as sleep } from "node:timers/promises";
import { createPowershellAdapter, type DaemonAdapter } from "./daemon-adapter.js";

export interface LaunchOptions {
  /** Absolute path to tools/mo2-vfs-launcher/xedit-client.ps1 (override for tests). */
  clientScript: string;
  /** xEdit launcher path (e.g. .artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe). */
  launcherPath: string;
  /** "Fallout4" / "Skyrim" / etc. */
  gameMode: string;
  /** MO2 profile name; default "Default". */
  moProfile?: string;
  /** Optional pre-allocated PID file the client writes (if any). */
  pidStateDir?: string;
  /** Timeout for daemon readiness, ms (default 60 000). */
  readyTimeoutMs?: number;
  pwshExe?: string;
}

export interface LaunchedDaemon {
  pid: number;
  adapter: DaemonAdapter;
  /** Best-effort teardown; daemon may continue running for further use. */
  stop: () => Promise<void>;
}

export async function launchDaemon(opts: LaunchOptions): Promise<LaunchedDaemon> {
  const pwsh = opts.pwshExe ?? "pwsh";
  const profile = opts.moProfile ?? "Default";

  // process launch — delegates to existing xedit-client.ps1
  const launchOut = await runPwshCapture(pwsh, [
    "-NoProfile", "-File", opts.clientScript,
    "process", "launch",
    "--launcher-path", opts.launcherPath,
    "--game-mode", opts.gameMode,
    "--mo-profile", profile,
  ]);

  // Parse the JSON envelope the client prints on success.
  const launchRes = JSON.parse(launchOut.trim());
  if (!launchRes.ok) {
    throw new Error(`xedit-client process launch refused: ${JSON.stringify(launchRes)}`);
  }
  const pid: number = launchRes.pid ?? launchRes.data?.pid;
  if (!pid) throw new Error("xedit-client launch returned no pid");

  // Wait for automation readiness via the client's wait command (or describe poll).
  const deadline = Date.now() + (opts.readyTimeoutMs ?? 60_000);
  while (Date.now() < deadline) {
    try {
      await runPwshCapture(pwsh, [
        "-NoProfile", "-File", opts.clientScript,
        "process", "wait",
        "--pid", String(pid),
      ]);
      break;
    } catch {
      await sleep(500);
    }
  }

  const adapter = createPowershellAdapter({
    clientScript: opts.clientScript,
    pid,
    scratchDir: join(tmpdir(), "xedit-mcp-calls", String(pid)),
    pwshExe: pwsh,
  });

  return {
    pid,
    adapter,
    stop: async () => {
      try {
        await runPwshCapture(pwsh, [
          "-NoProfile", "-File", opts.clientScript,
          "process", "stop", "--pid", String(pid),
        ]);
      } catch { /* best-effort */ }
    },
  };
}

function runPwshCapture(pwsh: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(pwsh, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "", stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(stdout);
      else reject(new Error(`pwsh exited ${code}: ${stderr.slice(0, 500)}`));
    });
  });
}
```

> The exact CLI flag names for `process launch | wait | stop` MUST be confirmed against `tools/mo2-vfs-launcher/xedit-client.ps1` and its dispatch table. Reconnaissance indicates these commands exist; adjust flags here if the actual names differ. The integration test below is what flushes these out — when it fails because of flag mismatches, fix `launch.ts` and re-run.

- [ ] **Step 3: Implement `tools/xedit-mcp/tests/integration/live-conflict-audit.test.ts`**

```ts
// tests/integration/live-conflict-audit.test.ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { buildServerToolset } from "../../src/index.js";
import { launchDaemon, type LaunchedDaemon } from "../../src/launch.js";

const REPO_ROOT = resolve(__dirname, "../../../../");
const CLIENT_SCRIPT = resolve(REPO_ROOT, "tools/mo2-vfs-launcher/xedit-client.ps1");
const LAUNCHER_PATH = resolve(
  REPO_ROOT,
  ".artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe",
);
const ARTIFACT_DIR = resolve(REPO_ROOT, ".opencode/artifacts/xedit-mcp/acceptance/batch1");
const FIXTURES = resolve(__dirname, "fixtures.json");

const ENABLED = process.env.XEDIT_MCP_INTEGRATION === "1";

describe.runIf(ENABLED)("W2 conflict audit — live daemon", () => {
  let daemon: LaunchedDaemon;
  let toolset: ReturnType<typeof buildServerToolset>;

  beforeAll(async () => {
    daemon = await launchDaemon({
      clientScript: CLIENT_SCRIPT,
      launcherPath: LAUNCHER_PATH,
      gameMode: "Fallout4",
      moProfile: "Default",
    });
    await mkdir(ARTIFACT_DIR, { recursive: true });
    toolset = buildServerToolset({
      adapter: daemon.adapter,
      sessionId: `batch1-${Date.now()}`,
      auditDir: resolve(ARTIFACT_DIR, "audit"),
      daemonPid: daemon.pid,
    });
  }, 90_000);

  afterAll(async () => {
    await daemon?.stop();
  });

  it("xedit_session returns ok with Fallout4 gameMode and a non-empty load order", async () => {
    const env = await toolset.invoke("xedit_session", {});
    await writeFile(resolve(ARTIFACT_DIR, "01-session.json"), JSON.stringify(env, null, 2));
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { gameMode: string }).gameMode).toBe("Fallout4");
    expect((env.data as { loadOrderSize: number }).loadOrderSize).toBeGreaterThan(0);
  });

  it("xedit_list_capabilities reports manageable drift", async () => {
    const env = await toolset.invoke("xedit_list_capabilities", {});
    await writeFile(resolve(ARTIFACT_DIR, "02-capabilities.json"), JSON.stringify(env, null, 2));
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const drift = (env.data as { drift: { onlyInLive: string[]; onlyInDigest: string[] } }).drift;
    // Soft assertion: report drift but do not fail unless catastrophically large
    expect(drift.onlyInLive.length + drift.onlyInDigest.length).toBeLessThan(50);
  });

  it("audits the three fixture records end-to-end", async () => {
    const fixtures = JSON.parse(await readFile(FIXTURES, "utf8")) as {
      records: Array<{ file: string; formId: string; expectedVerdict: string; note: string }>;
    };

    const results: unknown[] = [];
    for (const r of fixtures.records) {
      const envInspect = await toolset.invoke("xedit_inspect_conflicts", { file: r.file, formId: r.formId });
      const envRead = await toolset.invoke("xedit_read_record", { file: r.file, formId: r.formId });
      results.push({ fixture: r, inspect: envInspect, read: envRead });
    }
    await writeFile(resolve(ARTIFACT_DIR, "03-audit-results.json"), JSON.stringify(results, null, 2));

    // Soft assertion: at least one record audited without daemon_error.
    const anyOk = results.some(
      (r) => (r as { inspect: { ok: boolean } }).inspect.ok,
    );
    expect(anyOk).toBe(true);
  });
});
```

- [ ] **Step 4: Update `package.json` test scripts to include the live env gate**

Modify `tools/xedit-mcp/package.json`:

```json
"scripts": {
  "build": "tsc -p tsconfig.json",
  "start": "node dist/index.js",
  "test": "vitest run --exclude tests/integration",
  "test:watch": "vitest --exclude tests/integration",
  "test:integration": "cross-env XEDIT_MCP_INTEGRATION=1 vitest run tests/integration",
  "typecheck": "tsc -p tsconfig.json --noEmit"
}
```

And add `cross-env` to devDependencies:

```json
"devDependencies": {
  "@types/node": "^22.0.0",
  "cross-env": "^7.0.3",
  "typescript": "^5.5.0",
  "vitest": "^2.0.0"
}
```

Then:

```bash
cd tools/xedit-mcp
npm install
```

- [ ] **Step 5: Run unit tests still pass (must not regress)**

```bash
npm test
```

Expected: all unit tests PASS, integration suite skipped.

- [ ] **Step 6: Run the live integration test**

> Prerequisite: edit `tests/integration/fixtures.json` to point at three actual records in your `.artifacts/mo2/profiles/Default/plugins.txt`. Confirm `.artifacts/mo2/Stock Game/Fallout 4/Tools/OpenCodeXEdit/xEdit.exe` exists.

```bash
npm run test:integration
```

Expected: three integration tests PASS. Three artifact files written under `.opencode/artifacts/xedit-mcp/acceptance/batch1/`:
- `01-session.json`
- `02-capabilities.json`
- `03-audit-results.json`

If a step fails, inspect the artifact, fix the launch wiring or the verdict mapping, re-run. Do not lower the bar.

- [ ] **Step 7: Commit**

```bash
git add tools/xedit-mcp/src/launch.ts tools/xedit-mcp/tests/integration/ tools/xedit-mcp/package.json
git commit -m "test(xedit-mcp): live integration test for W2 conflict audit + production launch wiring"
```

---

### Task 24: Oracle semantic-acceptance review

**Files:**
- No code change. Outputs a review note at `.opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review.md`.

**Rationale:** Spec §13 mandates a reviewer-subagent pass before declaring a batch complete. The orchestrator is too close to its own work to grade it.

- [ ] **Step 1: Dispatch `@oracle` with the artifact paths**

In the controlling session, send the following prompt to `@oracle` (or the harness's strategic-review equivalent), with the three artifact files attached:

> Review the Batch 1 acceptance artifacts at `.opencode/artifacts/xedit-mcp/acceptance/batch1/01-session.json`, `02-capabilities.json`, `03-audit-results.json` against the design spec at `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md` (§5, §6, §9, §11 W2, §13). Judge semantic acceptance, not surface success:
>
> - Does the session envelope carry every field the hub skill promises?
> - Does the capabilities drift report make sense for the live daemon?
> - For each of the three audited records: is the verdict label consistent with the raw `records.conflict_status` status field? Is `winningOverride` present and resolvable in the load order? If `referencedBy` is non-empty, are the referencers plausible?
> - Are there any pipeline stages whose absence is observable in the artifacts (e.g. missing audit lines, raw daemon envelopes leaking)?
>
> Output: a markdown verdict (`accept | accept_with_followups | reject`) and a list of concrete follow-ups (rules to draft, drift to address, mapping fixes). Save to `.opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review.md`.

- [ ] **Step 2: Read the review; decide**

- If `accept` or `accept_with_followups` with non-blocking items, proceed to Phase H.
- If `reject`, fix the surfaced issues, re-run Task 23, and re-dispatch oracle.

- [ ] **Step 3: Commit the review artifact**

```bash
git add .opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review.md
git commit -m "docs(xedit-mcp): batch1 oracle semantic-acceptance review"
```

---

## Phase H — Documentation & Plan Close

### Task 25: Update roadmap + README pointers + close the batch

**Files:**
- Modify: `docs/roadmap.md` — refresh per project memory `30-operational-continuity-and-state-hygiene.md` rule 6
- Modify: `tools/README.md` — add a `xedit-mcp/` row
- Modify: `tools/xedit-mcp/README.md` — link the spec + plan + skill + acceptance artifacts
- Create: `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md` (per-batch status file)

**Rationale:** Project memory rule: after every implementation round, refresh the roadmap with "what was delivered / what is now known / what later phases must do differently." Batches 2-4 inherit Batch 1's learnings via these notes.

- [ ] **Step 1: Append to `docs/roadmap.md`**

Add a new dated entry under whatever the most recent section is. The entry MUST contain:

```markdown
### 2026-05-26 — Batch 1: xEdit harness MCP + skills (vertical slice)

**Delivered:**
- `tools/xedit-mcp/` TypeScript MCP server with pipeline stages [1][2][3][6][7], audit log, six tools (`xedit_session`, `xedit_list_capabilities`, `xedit_find_record`, `xedit_read_record`, `xedit_inspect_conflicts`, `xedit_call`).
- Seed rule `LOAD001` (CRITICAL) and registry mechanism for future rules.
- `.opencode/skills/xedit-automation/` hub + knowledgebase, and `xedit-conflict-audit` task skill.
- W2 conflict-audit workflow proven end-to-end against `.artifacts/mo2/` live daemon; acceptance artifacts under `.opencode/artifacts/xedit-mcp/acceptance/batch1/`.

**Now known (from real implementation):**
- Concrete `xedit-client.ps1` flag names for `process launch | wait | stop | automation call` are <fill from Task 5/Task 23 implementation>.
- Live `records.conflict_status` status strings are <fill from Task 23 artifacts>; mapping to verdict labels in `inspect-conflicts.ts` adjusted accordingly.
- MCP-PowerShell-daemon round-trip latency is <p50/p95 from Task 23 measurements>.
- Drift between curated digest and live capabilities is <count from Task 23>.

**Implications for batches 2-4:**
- Pipeline stages [4] snapshot and [5] preview can land in Batch 3 unchanged; the composer is ready to accept them.
- The `xedit_call` rule integration pattern (rules opt-in via `appliesTo`) handles both intent tools and atomic passthrough; later rules just declare both tool names.
- The integration test scaffold (fixtures + acceptance artifact pattern) is the template all later batches copy.

**Carry-forward / drift:**
- The xEdit fork's `-automation-mcp-mode` patch has not landed yet. The MCP sends `mcpToken` already; the daemon currently ignores it. When the fork patch ships, bypass closure activates with no MCP-side changes.
- `tools/xedit-hook-bridge/` retirement (per native-adoption design) is unrelated to this batch; defer.
```

> The three `<fill ...>` placeholders MUST be filled with actual values observed during Task 23 execution. Do not commit this file with placeholders intact.

- [ ] **Step 2: Add a row to `tools/README.md`**

Inspect `tools/README.md`, find the existing rows, and add (location: alphabetical or end, matching convention):

```markdown
- `xedit-mcp/` — TypeScript MCP server: harness pipeline over the forked xEdit daemon. See `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`.
```

- [ ] **Step 3: Expand `tools/xedit-mcp/README.md`**

Replace the Task 1 stub with a fuller readme:

```markdown
# xedit-mcp

Harness MCP server for the forked xEdit automation daemon.

- **Design spec:** `docs/superpowers/specs/2026-05-26-xedit-skills-and-harness-mcp-design.md`
- **Batch 1 plan:** `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.md`
- **Hub skill:** `.opencode/skills/xedit-automation/SKILL.md`
- **Knowledgebase:** `.opencode/skills/xedit-automation/xedit-knowledgebase.md`
- **W2 task skill:** `.opencode/skills/xedit-conflict-audit/SKILL.md`
- **Batch 1 acceptance artifacts:** `.opencode/artifacts/xedit-mcp/acceptance/batch1/`

## Status (Batch 1)

Shipped: 6 read-side tools + atomic passthrough, pipeline stages [1][2][3][6][7], LOAD001 rule, hub & W2 skills.

Not yet shipped: snapshot [4] / preview [5] (Batch 3), mutating tools (Batches 3-4), remaining 9 seed rules.

## Use

```bash
npm install
npm test                    # unit tests
npm run typecheck
npm run build
XEDIT_MCP_INTEGRATION=1 npm run test:integration   # live daemon, edit fixtures.json first
```

For production MCP usage, wire `buildServerToolset()` from `src/index.ts` with a `launchDaemon()` from `src/launch.ts`. See `tests/integration/live-conflict-audit.test.ts` for the canonical wiring.

## Pipeline

Every tool call traverses:

1. Schema validation (`zod`)
2. State precheck (daemon ready, load order, consent, mcp-mode)
3. Rule registry scan (CRITICAL/HIGH refuse; MEDIUM warns)
4. (Batch 3+) Snapshot before mutate
5. (Batch 3+) Preview + confirmToken for HIGH-RISK mutations
6. Forward to daemon via `tools/mo2-vfs-launcher/xedit-client.ps1`
7. Envelope shape + audit JSONL

Refusals carry `{code, hint, rationale, matched}` so the agent learns the correct path.
```

- [ ] **Step 4: Create the per-batch STATUS file**

```markdown
# Batch 1 Status

- **Plan:** `2026-05-26-xedit-skills-and-harness-mcp-batch1.md`
- **Status:** SHIPPED / IN-REVIEW / BLOCKED — fill in
- **Date completed:**
- **Oracle review verdict:** (link to `.opencode/artifacts/xedit-mcp/acceptance/batch1/oracle-review.md`)
- **Open follow-ups for Batch 2:**
  - …
```

- [ ] **Step 5: Final commit**

```bash
git add docs/roadmap.md tools/README.md tools/xedit-mcp/README.md docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.STATUS.md
git commit -m "docs: refresh roadmap and READMEs after xedit-mcp Batch 1"
```

---

## Self-Review (run after completing all 25 tasks)

### Spec coverage (per spec §, point to the task)

- §3 architecture diagram → Tasks 1-19 cumulatively realise the layered shape.
- §4 pipeline stages [1][2][3][6][7] → Tasks 7, 8, 9, 10, 11; stages [4][5] explicitly deferred to Batch 3 per spec §12.
- §5 Layer A intent tools (Batch 1 subset) → Tasks 13, 14, 15, 16, 17.
- §5 Layer B atomic passthrough → Task 18.
- §6 rule registry + LOAD001 seed → Task 9. Remaining 9 seed rules deferred to the batch that ships their target tools.
- §8 `mcpToken` carriage → Task 5 (adapter accepts `mcpToken`; sent to daemon; daemon currently ignores until fork patch).
- §9 hub + KB + task skill → Tasks 20, 21, 22.
- §10 routing doctrine → Task 20 (hub skill).
- §11 W2 workflow → Task 22 (skill) + Task 23 (verification).
- §13 semantic verification → Tasks 23 + 24.
- §14 risks: rules-as-knowledge growth path → covered by `rules/candidates/` reference in hub skill (Task 20).
- §16 envelope schema, error-code namespace, artifact layout, repo placement → all consumed by Tasks 2, 3, 4, 7-11.

### Placeholder scan

Search the plan you've executed against for `TBD`, `TODO`, `<fill...>`. The only allowed placeholders are the three `<fill from Task 23 ...>` markers in roadmap.md (Step 1 of Task 25), and the user-editable fixtures file (Task 23 Step 1). These MUST be filled before the final commit.

### Type consistency

- `ToolContext` (defined Task 2) is consumed identically by every tool (Tasks 13-18) — confirmed: same `loadOrder?`, `capabilities?`, `consentEnabled?`, `daemonPid?` fields.
- `Envelope` discriminated union (Task 2) — all tools return through `ok()`, `refuse()`, or `fromRuleFinding()` (Task 4) — no ad-hoc shapes.
- `Rule` shape (Task 2) is what `LOAD001` (Task 9) implements; registry (Task 9) consumes it.
- The pipeline composer (Task 11) takes `ToolSpec` with the same `schema`/`needs`/`command`/`summary` shape every tool feeds it.
- `DaemonAdapter` (Task 5) is what `forwardCall` (Task 10), `runTool` (Task 11), and all tools (13-18) consume; `launch.ts` (Task 23) constructs the production instance.

No naming inconsistencies found. Method names align across tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-26-xedit-skills-and-harness-mcp-batch1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Required sub-skill: `subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session with batch checkpoints. Required sub-skill: `executing-plans`.

Which approach?








