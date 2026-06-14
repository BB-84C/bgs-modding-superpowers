import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-rp-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+Current\n", "utf8");

  // Pre-create a backup
  const backupDir = join(root, ".mo2-mcp", "profile-backups", "Default_snap1");
  await mkdir(backupDir, { recursive: true });
  await writeFile(join(backupDir, "modlist.txt"), "+Backup\n+Restored\n", "utf8");
  await writeFile(join(backupDir, "plugins.txt"), "*Foo.esp\n", "utf8");

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

describe("mo2_restore_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-restore-profile.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_restore_profile")?.tier).toBe("T3");
  });

  it("plan → apply restores profile files from backup", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_restore_profile")!;
    const plan = (await tool.handler(
      { mode: "plan", profile: "Default", label: "snap1" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { restored: string[] } };
    expect(apply.ok).toBe(true);
    expect(apply.result.restored).toContain("modlist.txt");
    expect(apply.result.restored).toContain("plugins.txt");

    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toBe("+Backup\n+Restored\n");
  });

  it("plan throws backup_not_found for unknown label", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_restore_profile")!;
    await expect(
      tool.handler({ mode: "plan", profile: "Default", label: "no-such-label" }, ctx),
    ).rejects.toThrow(/backup_not_found/);
  });
});
