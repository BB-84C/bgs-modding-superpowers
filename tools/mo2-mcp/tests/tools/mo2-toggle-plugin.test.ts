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
  const root = await mkdtemp(join(tmpdir(), "mo2-tp-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "plugins.txt"),
    "*Fallout4.esm\n*EnabledMod.esp\nDisabled.esp\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
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

describe("mo2_toggle_plugin", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-toggle-plugin.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_toggle_plugin")?.tier).toBe("T3");
  });

  it("plan → apply enables a disabled plugin (offline)", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_toggle_plugin")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "Disabled.esp", enabled: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);
    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const plugins = await readFile(join(root, "profiles", "Default", "plugins.txt"), "utf8");
    expect(plugins).toContain("*Disabled.esp");
  });

  it("also_hide_file=true without pipe → plan throws", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_toggle_plugin")!;
    await expect(
      tool.handler(
        { mode: "plan", name: "EnabledMod.esp", enabled: false, also_hide_file: true },
        ctx,
      ),
    ).rejects.toThrow(/also_hide_file_requires_live_mo2/);
  });
});
