import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(
  pluginLines: string[] = ["*Base.esm", "*Anchor.esm", "*Source.esp", "*Last.esp"],
): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-send-plugin-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+SomeMod\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), pluginLines.join("\n") + "\n", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+SomeMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "*Source.esp\n", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]\ngame=fallout4\nselected_profile=Default\n[Settings]\nbase_directory=${root}\n`,
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
  return { root, ctx };
}

function _pipeClient(calls: Array<{ method: string; params: unknown }>): ToolContext["pipeClient"] {
  return {
    call: async (method: string, params: unknown) => {
      calls.push({ method, params });
      if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
      if (method === "plugins.set_priority") return { ok: true, result: { actual_priority: (params as { priority: number }).priority }, error: null };
      throw new Error(`unexpected broker method ${method}`);
    },
    close: () => {},
    discoverAndConnect: async () => {},
    isConnected: () => true,
  } as unknown as ToolContext["pipeClient"];
}

async function _plan(args: Record<string, unknown>, ctx: ToolContext): Promise<{ ok: boolean; result: { diff: string; plan_id: string; lease_token: string } }> {
  const tool = getTool("mo2_send_plugin_to")!;
  return await tool.handler({ mode: "plan", name: "Source.esp", ...args }, ctx) as {
    ok: boolean;
    result: { diff: string; plan_id: string; lease_token: string };
  };
}

describe("mo2_send_plugin_to", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-send-plugin-to.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_send_plugin_to")?.tier).toBe("T3");
  });

  it("gui_top maps to priority 0 in FORWARD plugins.txt space (loads first = loses)", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "gui_top" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 0");
    expect(plan.result.diff).toContain("gui_top (priority 0 = loads first = loses all)");
  });

  it("gui_bottom maps to priority N-1 (loads last = wins)", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "gui_bottom" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 3");
    expect(plan.result.diff).toContain("gui_bottom (priority 3 = loads last = wins all)");
  });

  it("wins_over targets anchor.priority + 1", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "wins_over", anchor: "Anchor.esm" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 2");
    expect(plan.result.diff).toContain("wins_over Anchor.esm");
  });

  it("loses_to targets anchor.priority - 1", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "loses_to", anchor: "Anchor.esm" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 0");
    expect(plan.result.diff).toContain("loses_to Anchor.esm");
  });

  it("raw_priority uses explicit priority and clamps to profile bounds", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "raw_priority", target_priority: 99 }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 3");
    expect(plan.result.diff).toContain("raw_priority 99");
  });

  it("apply live path invokes broker plugins.set_priority with FORWARD-space priority", async () => {
    const { ctx } = await _fixture();
    const calls: Array<{ method: string; params: unknown }> = [];
    ctx.pipeClient = _pipeClient(calls);
    const tool = getTool("mo2_send_plugin_to")!;
    const plan = await _plan({ target_mode: "wins_over", anchor: "Anchor.esm" }, ctx);

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { target_mode: string; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(calls.find((c) => c.method === "plugins.set_priority")?.params).toMatchObject({ name: "Source.esp", priority: 2 });
    expect(apply.result.target_mode).toBe("wins_over");
    expect(apply.result._meta).toEqual({
      priority_convention: "plugins_txt_forward_space_higher_wins",
      plugins_txt_file_order: "forward_matches_gui",
      gui_direction_hint: "priority_0_at_gui_top_loads_first_loses; priority_(N-1)_at_gui_bottom_loads_last_wins",
    });
  });

  it("offline apply rewrites plugins.txt in GUI/forward order", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_send_plugin_to")!;
    const plan = await _plan({ target_mode: "gui_top" }, ctx);

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { source: string; new_priority: number; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(apply.result.source).toBe("offline_plugins_txt_reorder");
    expect(apply.result.new_priority).toBe(0);
    expect(apply.result._meta.plugins_txt_file_order).toBe("forward_matches_gui");
    const pluginsTxt = await readFile(join(root, "profiles", "Default", "plugins.txt"), "utf8");
    expect(pluginsTxt.trim().split(/\r?\n/)).toEqual(["*Source.esp", "*Base.esm", "*Anchor.esm", "*Last.esp"]);
  });

  it("throws when wins_over is missing anchor", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "wins_over" }, ctx)).rejects.toThrow(/wins_over_requires_anchor/);
  });

  it("throws when anchor is unknown", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "wins_over", anchor: "Missing.esm" }, ctx)).rejects.toThrow(/anchor_not_found: Missing.esm/);
  });

  it("throws when raw_priority is missing target_priority", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "raw_priority" }, ctx)).rejects.toThrow(/raw_priority_requires_target_priority_int/);
  });

  it("throws when source plugin is missing", async () => {
    const { ctx } = await _fixture(["*Base.esm", "*Anchor.esm"]);

    await expect(_plan({ target_mode: "gui_bottom" }, ctx)).rejects.toThrow(/plugin_not_found: Source.esp/);
  });

  it("cross-profile live plan blocks when requested profile is not the active MO2 profile", async () => {
    const { ctx } = await _fixture();
    const calls: Array<{ method: string; params: unknown }> = [];
    ctx.pipeClient = _pipeClient(calls);

    await expect(
      _plan({ target_mode: "gui_top", profile: "BB84自用" }, ctx),
    ).rejects.toThrow(/cross_profile_live_mutation_blocked/);
  });
});
