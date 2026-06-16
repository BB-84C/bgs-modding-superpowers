import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-rb-"));
  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "full-control",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test-session",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test-session"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test-session"),
  };
  return { root, ctx };
}

describe("mo2_rollback", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-rollback.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_rollback")?.tier).toBe("T3");
  });

  it("snapshot → mutate → rollback restores original content", async () => {
    const { root, ctx } = await _fixture();
    const target = join(root, "data.txt");
    await writeFile(target, "original\n", "utf8");

    // Snapshot
    const record = await ctx.snapshots.snapshot("test_tool", [target]);

    // Mutate
    await writeFile(target, "MUTATED\n", "utf8");

    // Rollback via tool
    const tool = getTool("mo2_rollback")!;
    const plan = (await tool.handler({ mode: "plan", snapshot_id: record.snapshotId }, ctx)) as {
      ok: boolean;
      result: { planId: string; lease_token: string };
    };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    expect(await readFile(target, "utf8")).toBe("original\n");
  });

  it("plan throws snapshot_not_found for unknown id", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_rollback")!;
    await expect(
      tool.handler({ mode: "plan", snapshot_id: "no-such-uuid" }, ctx),
    ).rejects.toThrow(/snapshot_not_found/);
  });
});
