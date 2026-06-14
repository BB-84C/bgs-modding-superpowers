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
  const root = await mkdtemp(join(tmpdir(), "mo2-is-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await writeFile(
    join(root, "profiles", "Default", "fallout4Prefs.ini"),
    "[Display]\niResolutionX=1920\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+ModA\n", "utf8");
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

describe("mo2_profile_ini_set", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-profile-ini-set.js");
  });

  it("registers as T2", () => {
    expect(getTool("mo2_profile_ini_set")?.tier).toBe("T2");
  });

  it("plan → apply updates existing key", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_profile_ini_set")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        profile: "Default",
        ini_name: "prefs",
        section: "Display",
        key: "iResolutionX",
        value: "2560",
      },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const text = await readFile(
      join(root, "profiles", "Default", "fallout4Prefs.ini"),
      "utf8",
    );
    expect(text).toContain("iResolutionX=2560");
  });
});
