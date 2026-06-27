import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(withPipe = true): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-sep-gui-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), ["+TopMod", "+AnchorMod", "+BottomMod", ""].join("\n"), "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+AnchorMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "mods"), { recursive: true });
  await writeFile(join(root, "ModOrganizer.ini"), `[General]\ngame=fallout4\nselected_profile=Default\n[Settings]\nbase_directory=${root}\n`, "utf8");

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
      call: async (method: string, params: Record<string, unknown>) => {
        if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
        return { ok: true, result: { name: params.name, created: true, priority: params.priority } };
      },
      close: () => {},
      discoverAndConnect: async () => {},
      isConnected: () => true,
    } as unknown as ToolContext["pipeClient"];
  }
  return { root, ctx };
}

describe("mo2_create_separator", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-create-separator.js");
  });

  it("plan throws live_mo2_required when pipeClient is absent", async () => {
    const { ctx } = await _fixture(false);
    const tool = getTool("mo2_create_separator")!;

    await expect(tool.handler({ mode: "plan", name: "Section" }, ctx)).rejects.toThrow(/live_mo2_required/);
  });

  it("plan with wins_over returns diff mentioning target priority and _separator name", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_separator")!;

    const plan = await tool.handler({ mode: "plan", name: "Section", wins_over: "AnchorMod", color: "#aabbcc" }, ctx) as {
      ok: boolean;
      result: { diff: string };
    };

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain('Create separator "Section" → Section_separator');
    expect(plan.result.diff).toContain("wins_over AnchorMod, pri=2");
    expect(plan.result.diff).toContain("color=#aabbcc");
  });

  it("plan throws wins_over_mod_not_found when wins_over name is absent", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_separator")!;

    await expect(tool.handler({ mode: "plan", name: "Section", wins_over: "Missing" }, ctx)).rejects.toThrow(/wins_over_mod_not_found: Missing/);
  });

  it("schema rejects empty wins_over at the Zod layer", async () => {
    const tool = getTool("mo2_create_separator")!;

    expect(tool.inputSchema.safeParse({ mode: "plan", name: "Section", wins_over: "" }).success).toBe(false);
  });

  it("schema rejects old above field at the Zod layer", async () => {
    const tool = getTool("mo2_create_separator")!;

    expect(tool.inputSchema.safeParse({ mode: "plan", name: "Section", above: "AnchorMod" }).success).toBe(false);
  });

  it("apply creates suffixed separator with wins_over priority, writes color meta, invalidates, and returns metadata", async () => {
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
    const tool = getTool("mo2_create_separator")!;
    const plan = await tool.handler({ mode: "plan", name: "Section", wins_over: "AnchorMod", color: "#aabbcc" }, ctx) as {
      ok: boolean;
      result: { planId: string; lease_token: string };
    };

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { separator_name: string; color_set: boolean; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ separator_name: "Section_separator", color_set: true });
    expect(pipeCalls).toEqual([
      { method: "profile.active", params: {} },
      { method: "profile.active", params: {} },
      { method: "mods.create", params: { name: "Section_separator", priority: 2 } },
      {
        method: "system.log_apply",
        params: expect.objectContaining({
          tool: "mo2_create_separator",
          profile: "Default",
          summary: "created separator \"Section_separator\" wins_over=\"AnchorMod\" → priority 2",
        }),
      },
    ]);
    expect(await readFile(join(root, "mods", "Section_separator", "meta.ini"), "utf8")).toBe("[General]\ncolor=#aabbcc\n");
    expect(sidecarCalls).toEqual([{ method: "world.invalidate", params: { profile_dir: join(root, "profiles", "Default") } }]);
    expect(apply.result._meta).toEqual({
      priority_convention: "mobase_full_space_higher_wins",
      modlist_file_order: "reverse_of_gui",
      gui_direction_hint: "priority_0_at_gui_top_loses; priority_(N-1)_at_gui_bottom_wins",
    });
  });

  it("apply without wins_over calls mods.create without priority and returns metadata", async () => {
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
    ctx.sidecar = {
      call: async () => ({ invalidated: true }),
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];
    const tool = getTool("mo2_create_separator")!;
    const plan = await tool.handler({ mode: "plan", name: "Plain" }, ctx) as { ok: boolean; result: { planId: string; lease_token: string } };

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { separator_name: string; color_set: boolean; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(apply.result).toMatchObject({ separator_name: "Plain_separator", color_set: false });
    expect(pipeCalls.find((c) => c.method === "mods.create")?.params).toEqual({ name: "Plain_separator" });
    expect(existsSync(join(root, "mods", "Plain_separator", "meta.ini"))).toBe(false);
    expect(apply.result._meta.priority_convention).toBe("mobase_full_space_higher_wins");
  });

  it("cross-profile live plan blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_create_separator")!;

    await expect(tool.handler({ mode: "plan", name: "Section", wins_over: "AnchorMod", profile: "BB84自用" }, ctx)).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
