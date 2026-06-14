import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-bm-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods", "ModA", "Data"), { recursive: true });
  await writeFile(join(root, "mods", "ModA", "Data", "foo.esp"), "ESP", "utf8");

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, ".mo2-mcp", "snapshots"),
      auditRoot: join(root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(root, ".mo2-mcp", "audit"), "test"),
  };
  return { root, ctx };
}

describe("mo2_backup_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-backup-mod.js");
  });

  it("registers as T2", () => {
    expect(getTool("mo2_backup_mod")?.tier).toBe("T2");
  });

  it("plan → apply copies mod to <name>backup0", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_backup_mod")!;
    const plan = (await tool.handler({ mode: "plan", name: "ModA" }, ctx)) as {
      ok: boolean;
      result: { planId: string; lease_token: string };
    };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { backup_name: string } };
    expect(apply.ok).toBe(true);
    expect(apply.result.backup_name).toBe("ModAbackup0");

    expect(existsSync(join(root, "mods", "ModAbackup0", "Data", "foo.esp"))).toBe(true);
  });

  it("finds next free slot when backup0 exists", async () => {
    const { root, ctx } = await _fixture();
    await mkdir(join(root, "mods", "ModAbackup0"), { recursive: true });
    const tool = getTool("mo2_backup_mod")!;
    const plan = (await tool.handler({ mode: "plan", name: "ModA" }, ctx)) as {
      ok: boolean;
      result: { planId: string; lease_token: string };
    };
    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { backup_name: string } };
    expect(apply.result.backup_name).toBe("ModAbackup1");
  });
});
