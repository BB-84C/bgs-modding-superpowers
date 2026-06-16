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

async function _fixture(withPipe = true): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-create-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    ["+TopMod", "+AnchorMod", "+BottomMod", ""].join("\n"),
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), ["+AnchorMod", ""].join("\n"), "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "mods"), { recursive: true });
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\n[Settings]\nbase_directory=${root}\n`,
    "utf8",
  );

  const ctx: ToolContext = {
    config: {
      mo2Root: root,
      permissionCeiling: "full-control",
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
  if (withPipe) {
    ctx.pipeClient = {
      call: async (method: string) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        return { ok: true, result: { name: "NewEmpty", created: true, priority: 2 } };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
  }
  return { root, ctx };
}

describe("mo2_create_mod", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-create-mod.js");
  });

  it("plan throws live_mo2_required_for_create_mod when pipeClient is absent", async () => {
    const { ctx } = await _fixture(false);
    const tool = getTool("mo2_create_mod")!;

    await expect(
      tool.handler({ mode: "plan", name: "NewEmpty" }, ctx),
    ).rejects.toThrow(/live_mo2_required_for_create_mod/);
  });

  it("plan with above returns diff mentioning target priority", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_mod")!;

    const plan = (await tool.handler(
      { mode: "plan", name: "NewEmpty", above: "AnchorMod" },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("above AnchorMod (pri=2)");
    expect(plan.result.affected_files[0]).toContain(join("profiles", "Default", "modlist.txt"));
  });

  it("plan throws above_mod_not_found when above name is absent", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_mod")!;

    await expect(
      tool.handler({ mode: "plan", name: "NewEmpty", above: "Missing" }, ctx),
    ).rejects.toThrow(/above_mod_not_found: Missing/);
  });

  it("apply calls mods.create with name and priority, ensures mod folder exists, then invalidates sidecar world", async () => {
    const { root, ctx } = await _fixture();
    const pipeCalls: Array<{ method: string; params: Record<string, unknown> }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        return { ok: true, result: { name: params.name, created: true, priority: params.priority } };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const sidecarCalls: Array<{ method: string; params: unknown }> = [];
    ctx.sidecar = {
      call: async (method: string, params: unknown) => {
        sidecarCalls.push({ method, params });
        return { invalidated: true };
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_create_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "NewEmpty", above: "AnchorMod" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; result: { name: string; created: boolean; priority: number } };

    expect(apply.ok).toBe(true);
    expect(pipeCalls).toEqual([
      { method: "profile.active", params: {} },
      { method: "mods.create", params: { name: "NewEmpty", priority: 2 } },
    ]);
    expect(existsSync(join(root, "mods", "NewEmpty"))).toBe(true);
    expect(sidecarCalls).toEqual([
      { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } },
    ]);
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
    const tool = getTool("mo2_create_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "NewEmpty", above: "AnchorMod", profile: "BB84自用" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    await expect(tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
