import { describe, it, expect, beforeAll } from "vitest";
import { z } from "zod";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, registerTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { dispatchToolCall } from "../../src/dispatch.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-aq-"));
  const auditRoot = join(root, ".mo2-mcp", "audit");
  await mkdir(auditRoot, { recursive: true });

  const today = new Date().toISOString().slice(0, 10);
  const auditPath = join(auditRoot, `test-session-${today}.jsonl`);
  await writeFile(
    auditPath,
    [
      JSON.stringify({ ts: "2026-06-14T10:00:00Z", sessionId: "test-session", tool: "mo2_status", argsHash: "h1", decision: "ok", durationMs: 5 }),
      JSON.stringify({ ts: "2026-06-14T10:01:00Z", sessionId: "test-session", tool: "mo2_toggle_mod", mode: "plan", argsHash: "h2", decision: "plan_generated", durationMs: 10, plan_id: "plan-A" }),
      JSON.stringify({ ts: "2026-06-14T10:02:00Z", sessionId: "test-session", tool: "mo2_toggle_mod", mode: "apply", argsHash: "h3", decision: "lease_violation", durationMs: 3 }),
    ].join("\n") + "\n",
    "utf8",
  );

  return {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot,
    },
    sessionId: "test-session",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test-session"),
    audit: new AuditLogger(auditRoot, "test-session"),
  };
}

describe("mo2_audit_query", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-audit-query.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_audit_query")?.tier).toBe("T1");
  });

  it("returns all records when no filter", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { records: Array<Record<string, unknown>>; count: number };
    };
    expect(result.ok).toBe(true);
    expect(result.result.count).toBe(3);
  });

  it("filters by tool name", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({ tool: "mo2_status" }, ctx)) as {
      ok: boolean;
      result: { count: number; records: Array<{ tool: string }> };
    };
    expect(result.result.count).toBe(1);
    expect(result.result.records[0].tool).toBe("mo2_status");
  });

  it("filters by decision", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({ decision: "lease_violation" }, ctx)) as {
      ok: boolean;
      result: { count: number };
    };
    expect(result.result.count).toBe(1);
  });

  it("filters by plan_id", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({ plan_id: "plan-A" }, ctx)) as {
      ok: boolean;
      result: { count: number };
    };
    expect(result.result.count).toBe(1);
  });

  it("query by plan_id returns dispatch audit records for plan and apply", async () => {
    const ctx = await _fixture();
    registerTool({
      name: "test_audit_plan_apply",
      tier: "T2",
      description: "test tool for audit plan_id logging",
      inputSchema: z.object({ mode: z.enum(["plan", "apply"]) }),
      handler: async (args) => {
        if (args.mode === "plan") {
          return { ok: true, result: { plan_id: "plan-dispatch", lease_token: "lease" } };
        }
        return { ok: true, result: { mode: "apply", plan_id: "plan-dispatch", snapshot_id: "snap-1" } };
      },
    });
    await dispatchToolCall({ toolName: "test_audit_plan_apply", rawArgs: { mode: "plan" }, ctx, rules: [] });
    await dispatchToolCall({ toolName: "test_audit_plan_apply", rawArgs: { mode: "apply" }, ctx, rules: [] });

    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({ plan_id: "plan-dispatch", max_results: 10 }, ctx)) as {
      ok: boolean;
      result: { count: number; records: Array<Record<string, unknown>> };
    };

    expect(result.result.count).toBe(2);
    expect(result.result.records.map((record) => record.plan_id)).toEqual([
      "plan-dispatch",
      "plan-dispatch",
    ]);
  });

  it("respects max_results with truncated flag", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_audit_query")!;
    const result = (await tool.handler({ max_results: 2 }, ctx)) as {
      ok: boolean;
      result: { count: number; truncated: boolean };
    };
    expect(result.result.count).toBe(2);
    expect(result.result.truncated).toBe(true);
  });
});
