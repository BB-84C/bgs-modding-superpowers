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
  const root = await mkdtemp(join(tmpdir(), "mo2-tm-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    "+TopMod\n-DisabledMod\n+MyGroup_separator\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+TopMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
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

describe("mo2_toggle_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-toggle-mod.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_toggle_mod")?.tier).toBe("T3");
  });

  it("plan → apply disables an enabled mod (offline)", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_toggle_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "TopMod", enabled: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toContain("-TopMod");
    expect(modlist).not.toContain("+TopMod");
  });

  it("plan → apply enables a disabled mod", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_toggle_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "DisabledMod", enabled: true },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist).toContain("+DisabledMod");
  });

  it("plan throws mod_not_found for nonexistent mod", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_toggle_mod")!;
    await expect(
      tool.handler({ mode: "plan", name: "NoSuch", enabled: true }, ctx),
    ).rejects.toThrow(/mod_not_found/);
  });

  it("lease_violation when modlist mutated between plan and apply", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_toggle_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "TopMod", enabled: false },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await writeFile(
      join(root, "profiles", "Default", "modlist.txt"),
      "+EXTERNAL\n",
      "utf8",
    );

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; error?: { code: string } };
    expect(apply.ok).toBe(false);
    expect(apply.error?.code).toBe("lease_violation");
  });

  it("live apply blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture();
    ctx.pipeClient = {
      call: async (method: string) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        throw new Error(`unexpected live mutation: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_toggle_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "TopMod", enabled: false, profile: "BB84自用" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await expect(tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
