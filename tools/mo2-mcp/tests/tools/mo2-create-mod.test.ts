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

  // BUG-20 fix (2026-06-17): some OpenCode tool-call surfaces emit `above: ""`
  // for the semantically-optional field, which used to interpolate into the
  // error message as `above_mod_not_found: ` (trailing space). The handler
  // now treats empty-string the same as the field being absent: skip lookup
  // and place the new mod at the bottom (no above-text in the diff).
  it("BUG-20: plan with above:'' is treated as absent and places mod at bottom", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_mod")!;

    const plan = (await tool.handler(
      { mode: "plan", name: "NewEmpty", above: "" },
      ctx,
    )) as { ok: boolean; result: { diff: string; affected_files: string[] } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toBe("Create empty mod NewEmpty");
    expect(plan.result.diff).not.toContain("above");
    expect(plan.result.diff).not.toContain("pri=");
    expect(plan.result.affected_files[0]).toContain(join("profiles", "Default", "modlist.txt"));
  });

  it("BUG-20: plan with above omitted is treated as absent and places mod at bottom", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_mod")!;

    const plan = (await tool.handler(
      { mode: "plan", name: "NewEmpty" },
      ctx,
    )) as { ok: boolean; result: { diff: string } };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toBe("Create empty mod NewEmpty");
  });

  it("BUG-20: apply with above:'' is treated as absent (mods.create called without priority)", async () => {
    const { root, ctx } = await _fixture();
    const pipeCalls: Array<{ method: string; params: Record<string, unknown> }> = [];
    ctx.pipeClient = {
      call: async (method: string, params: Record<string, unknown>) => {
        pipeCalls.push({ method, params });
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        return { ok: true, result: { name: params.name, created: true } };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    ctx.sidecar = {
      call: async () => ({ invalidated: true }),
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_create_mod")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "BottomMod2", above: "" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };

    expect(apply.ok).toBe(true);
    const createCall = pipeCalls.find((c) => c.method === "mods.create");
    expect(createCall).toBeDefined();
    // No `priority` key — falls to bottom on the MO2 side.
    expect(createCall!.params).toEqual({ name: "BottomMod2" });
    expect(existsSync(join(root, "mods", "BottomMod2"))).toBe(true);
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
    // BUG-9 fix (2026-06-17): buildPlan now also runs assertActiveProfile,
    // which adds an extra profile.active call before the apply-time guard.
    expect(pipeCalls).toEqual([
      { method: "profile.active", params: {} }, // buildPlan guard
      { method: "profile.active", params: {} }, // applyMutation guard
      { method: "mods.create", params: { name: "NewEmpty", priority: 2 } },
    ]);
    expect(existsSync(join(root, "mods", "NewEmpty"))).toBe(true);
    expect(sidecarCalls).toEqual([
      { method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } },
    ]);
  });

  // BUG-9 fix (2026-06-17): cross-profile request is rejected at plan time,
  // not only at apply time. The plan envelope never lands in the agent's
  // hand if MO2 is live on a different profile.
  it("BUG-9: live plan blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture();
    ctx.pipeClient = {
      call: async (method: string) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        throw new Error(`unexpected broker call during plan: ${method}`);
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
    const tool = getTool("mo2_create_mod")!;

    await expect(tool.handler(
      { mode: "plan", name: "NewEmpty", above: "AnchorMod", profile: "BB84自用" },
      ctx,
    )).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
