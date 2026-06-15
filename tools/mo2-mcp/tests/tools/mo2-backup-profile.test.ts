import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-bp-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+ModA\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "*Fallout4.esm\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "settings.txt"), "key=value\n", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );

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

describe("mo2_backup_profile", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-backup-profile.js");
  });

  it("registers as T2", () => {
    expect(getTool("mo2_backup_profile")?.tier).toBe("T2");
  });

  it("plan → apply copies .txt files to backup label", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_backup_profile")!;
    const plan = (await tool.handler({ mode: "plan", profile: "Default", label: "snap1" }, ctx)) as {
      ok: boolean;
      result: { planId: string; lease_token: string };
    };
    expect(plan.ok).toBe(true);
    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as {
      ok: boolean;
      result: { backup_label: string; files_backed_up: number };
    };
    expect(apply.ok).toBe(true);
    expect(apply.result.backup_label).toBe("snap1");
    expect(apply.result.files_backed_up).toBeGreaterThanOrEqual(3);

    const backupDir = join(root, ".mo2-mcp", "profile-backups", "Default_snap1");
    const files = await readdir(backupDir);
    expect(files).toContain("modlist.txt");
    expect(files).toContain("plugins.txt");
    expect(files).toContain("settings.txt");

    const modlist = await readFile(join(backupDir, "modlist.txt"), "utf8");
    expect(modlist).toBe("+ModA\n");
  });
});
