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

/**
 * Mock pipeClient. brokerPlugins simulates the broker's `plugins.list`
 * response — a flat list of name/priority pairs in mobase priority space.
 * For Starfield-style fixtures, this includes a foreign-officials prefix
 * (e.g., priorities 0..11) so we can prove the live path uses mobase
 * priorities, NOT plugins.txt forward-index space.
 */
function _pipeClient(
  calls: Array<{ method: string; params: unknown }>,
  brokerPlugins: Array<{ name: string; priority: number }> = [
    { name: "Base.esm", priority: 0 },
    { name: "Anchor.esm", priority: 1 },
    { name: "Source.esp", priority: 2 },
    { name: "Last.esp", priority: 3 },
  ],
): ToolContext["pipeClient"] {
  return {
    call: async (method: string, params: unknown) => {
      calls.push({ method, params });
      if (method === "profile.active") return { ok: true, result: { name: "Default" }, error: null };
      if (method === "plugins.list") {
        return {
          ok: true,
          result: { plugins: brokerPlugins.map((p) => ({ name: p.name, priority: p.priority })) },
          error: null,
        };
      }
      if (method === "plugins.set_priority") {
        return { ok: true, result: { actual_priority: (params as { priority: number }).priority }, error: null };
      }
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

  describe("OFFLINE path (no broker, plugins.txt index space)", () => {
    it("gui_top maps to priority 0 in FORWARD plugins.txt space (loads first = loses)", async () => {
      const { ctx } = await _fixture();
      const plan = await _plan({ target_mode: "gui_top" }, ctx);

      expect(plan.ok).toBe(true);
      expect(plan.result.diff).toContain("priority 0");
      expect(plan.result.diff).toContain("[plugins_txt_index]");
      expect(plan.result.diff).toContain("gui_top (priority 0 = loads first = loses all)");
    });

    it("gui_bottom maps to priority N-1 (loads last = wins)", async () => {
      const { ctx } = await _fixture();
      const plan = await _plan({ target_mode: "gui_bottom" }, ctx);

      expect(plan.ok).toBe(true);
      expect(plan.result.diff).toContain("priority 3");
      expect(plan.result.diff).toContain("[plugins_txt_index]");
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
      expect(apply.result._meta.priority_space).toBe("plugins_txt_index");
      const pluginsTxt = await readFile(join(root, "profiles", "Default", "plugins.txt"), "utf8");
      expect(pluginsTxt.trim().split(/\r?\n/)).toEqual(["*Source.esp", "*Base.esm", "*Anchor.esm", "*Last.esp"]);
    });
  });

  describe("LIVE path (broker, mobase priority space)", () => {
    it("wins_over uses anchor's mobase priority (not plugins.txt index) — issue #20 Bug 1 regression", async () => {
      // Starfield-style fixture: 12 foreign officials at priorities 0..11,
      // then the user plugins at 12..15. anchor.mobase_priority = 13.
      const brokerPlugins = [
        ...Array.from({ length: 12 }, (_, i) => ({ name: `Official${i}.esm`, priority: i })),
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const tool = getTool("mo2_send_plugin_to")!;
      const plan = await _plan({ target_mode: "wins_over", anchor: "Anchor.esm" }, ctx);

      // The OLD buggy code would have returned priority 2 (TS index of Anchor.esm + 1).
      // The fixed code returns 14 (Anchor.esm's mobase priority + 1).
      expect(plan.result.diff).toContain("priority 14");
      expect(plan.result.diff).toContain("[mobase]");

      const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
        ok: boolean;
        result: { target_mode: string; new_priority: number; _meta: Record<string, string> };
      };

      expect(apply.ok).toBe(true);
      expect(calls.find((c) => c.method === "plugins.set_priority")?.params).toMatchObject({
        name: "Source.esp",
        priority: 14,
      });
      expect(apply.result.new_priority).toBe(14);
      expect(apply.result.target_mode).toBe("wins_over");
      expect(apply.result._meta.priority_space).toBe("mobase");
    });

    it("gui_bottom targets MAX mobase priority across plugins.txt entries — issue #20 Bug 2 regression", async () => {
      // BB84-like Starfield fixture: 12 officials + 4 user plugins, max user
      // priority = 15. The OLD buggy code would have returned priority 3
      // (TS plugins.length - 1). The fixed code returns 15.
      const brokerPlugins = [
        ...Array.from({ length: 12 }, (_, i) => ({ name: `Official${i}.esm`, priority: i })),
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const tool = getTool("mo2_send_plugin_to")!;
      const plan = await _plan({ target_mode: "gui_bottom" }, ctx);

      expect(plan.result.diff).toContain("priority 15");
      expect(plan.result.diff).toContain("[mobase]");

      const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
        ok: boolean;
        result: { new_priority: number };
      };

      expect(calls.find((c) => c.method === "plugins.set_priority")?.params).toMatchObject({
        name: "Source.esp",
        priority: 15,
      });
      expect(apply.result.new_priority).toBe(15);
    });

    it("gui_top targets MIN priority among plugins.txt entries (skips foreign officials)", async () => {
      const brokerPlugins = [
        ...Array.from({ length: 12 }, (_, i) => ({ name: `Official${i}.esm`, priority: i })),
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const tool = getTool("mo2_send_plugin_to")!;
      const plan = await _plan({ target_mode: "gui_top" }, ctx);

      // gui_top = min(plugins.txt entries) = 12 (skips officials at 0..11)
      expect(plan.result.diff).toContain("priority 12");
      expect(plan.result.diff).toContain("[mobase]");
    });

    it("loses_to targets anchor.mobase_priority - 1", async () => {
      const brokerPlugins = [
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const plan = await _plan({ target_mode: "loses_to", anchor: "Anchor.esm" }, ctx);

      expect(plan.result.diff).toContain("priority 12");
      expect(plan.result.diff).toContain("loses_to Anchor.esm");
    });

    it("raw_priority clamps to mobase max priority of plugins.txt entries", async () => {
      const brokerPlugins = [
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const plan = await _plan({ target_mode: "raw_priority", target_priority: 9999 }, ctx);

      expect(plan.result.diff).toContain("priority 15");
    });

    it("apply response carries mobase priority_space marker", async () => {
      const brokerPlugins = [
        { name: "Base.esm", priority: 12 },
        { name: "Anchor.esm", priority: 13 },
        { name: "Source.esp", priority: 14 },
        { name: "Last.esp", priority: 15 },
      ];
      const { ctx } = await _fixture();
      const calls: Array<{ method: string; params: unknown }> = [];
      ctx.pipeClient = _pipeClient(calls, brokerPlugins);
      const tool = getTool("mo2_send_plugin_to")!;
      const plan = await _plan({ target_mode: "wins_over", anchor: "Anchor.esm" }, ctx);
      const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
        ok: boolean;
        result: { _meta: Record<string, string> };
      };

      expect(apply.result._meta).toEqual({
        priority_convention: "mobase_full_space_higher_wins",
        plugins_txt_file_order: "forward_matches_gui",
        gui_direction_hint:
          "priority is mobase IPluginList space; foreign officials occupy a leading prefix; higher_priority_wins",
        priority_space: "mobase",
      });
    });
  });

  describe("error paths", () => {
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
});
