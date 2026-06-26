import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { dispatchToolCall } from "../../src/dispatch.js";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(
  modlistLines: string[] = [
    "+TopMod",
    "+ZoneMod1",
    "+ZoneMod2",
    "+版本已过期_separator",
    "+BelowMod1",
    "+MidSection_separator",
    "+SourceMod",
    "+BelowMod2",
    "+BottomSection_separator",
    "+BelowMod3",
    "+BelowMod4",
    "+BottomMod",
  ],
): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-send-gui-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), modlistLines.join("\n") + "\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await mkdir(join(root, "profiles", "BB84自用"), { recursive: true });
  await writeFile(join(root, "profiles", "BB84自用", "modlist.txt"), "+SourceMod\n", "utf8");
  await writeFile(join(root, "profiles", "BB84自用", "plugins.txt"), "", "utf8");
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
      if (method === "mods.set_priority") return { ok: true, result: { actual_priority: (params as { priority: number }).priority }, error: null };
      throw new Error(`unexpected broker method ${method}`);
    },
    close: () => {},
    discoverAndConnect: async () => {},
    isConnected: () => true,
  } as unknown as ToolContext["pipeClient"];
}

async function _plan(args: Record<string, unknown>, ctx: ToolContext): Promise<{ ok: boolean; result: { diff: string; plan_id: string; lease_token: string } }> {
  const tool = getTool("mo2_send_mod_to")!;
  return await tool.handler({ mode: "plan", name: "SourceMod", ...args }, ctx) as {
    ok: boolean;
    result: { diff: string; plan_id: string; lease_token: string };
  };
}

describe("mo2_send_mod_to", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-send-mod-to.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_send_mod_to")?.tier).toBe("T3");
  });

  it("gui_top maps to priority 0 (NOT to highest priority)", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "gui_top" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 0");
    expect(plan.result.diff).toContain("gui_top (priority 0 = loses all)");
  });

  it("gui_bottom maps to priority N-1 (NOT to priority 0)", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "gui_bottom" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 11");
    expect(plan.result.diff).toContain("gui_bottom (priority 11 = wins all)");
  });

  it("wins_over targets anchor.priority + 1", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "wins_over", anchor: "BelowMod1" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 8");
    expect(plan.result.diff).toContain("wins_over BelowMod1");
  });

  it("loses_to targets anchor.priority - 1", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "loses_to", anchor: "BelowMod1" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 6");
    expect(plan.result.diff).toContain("loses_to BelowMod1");
  });

  it("wins_over: separator places mod inside section labeled by that separator", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "wins_over", anchor: "版本已过期_separator" }, ctx);

    expect(plan.ok).toBe(true);
    // Fixture: separator priority 8; wins_over means sep.priority + 1 = 9,
    // which is inside that labeled section at the top visual position.
    expect(plan.result.diff).toContain("priority 9");
    expect(plan.result.diff).toContain("wins_over 版本已过期_separator");
  });

  it("loses_to: separator places mod outside section, visually above separator header", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "loses_to", anchor: "版本已过期_separator" }, ctx);

    expect(plan.ok).toBe(true);
    // Fixture: separator priority 8; loses_to means sep.priority - 1 = 7,
    // which is outside that section (the section above in GUI terms).
    expect(plan.result.diff).toContain("priority 7");
    expect(plan.result.diff).toContain("loses_to 版本已过期_separator");
  });

  it("raw_priority uses explicit priority and clamps to profile bounds", async () => {
    const { ctx } = await _fixture();
    const plan = await _plan({ target_mode: "raw_priority", target_priority: 99 }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 11");
    expect(plan.result.diff).toContain("raw_priority 99");
  });

  it("wins_over_conflicts targets max conflict priority + 1", async () => {
    const { ctx } = await _fixture(["+ConflictWinner", "+SourceMod", "+Neutral_separator", "+ConflictLoser", "+BottomMod"]);
    ctx.sidecar = {
      call: async (method: string) => {
        expect(method).toBe("assets.conflicts");
        return { conflicts: [{ providers: ["SourceMod", "ConflictWinner", "ConflictLoser"] }] };
      },
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];

    const plan = await _plan({ target_mode: "wins_over_conflicts" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 4");
    expect(plan.result.diff).toContain("wins_over_conflicts (top of conflict set)");
  });

  it("loses_to_conflicts targets min conflict priority - 1", async () => {
    const { ctx } = await _fixture(["+ConflictWinner", "+SourceMod", "+Neutral_separator", "+ConflictLoser", "+BottomMod"]);
    ctx.sidecar = {
      call: async () => ({ conflicts: [{ providers: ["SourceMod", "ConflictWinner", "ConflictLoser"] }] }),
      isReady: () => true,
      start: async () => {},
      stop: async () => {},
    } as unknown as ToolContext["sidecar"];

    const plan = await _plan({ target_mode: "loses_to_conflicts" }, ctx);

    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("priority 0");
    expect(plan.result.diff).toContain("loses_to_conflicts (bottom of conflict set)");
  });

  it("apply response includes GUI-aligned metadata", async () => {
    const { ctx } = await _fixture();
    const calls: Array<{ method: string; params: unknown }> = [];
    ctx.pipeClient = _pipeClient(calls);
    const tool = getTool("mo2_send_mod_to")!;
    const plan = await _plan({ target_mode: "wins_over", anchor: "版本已过期_separator" }, ctx);

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { target_mode: string; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(calls.find((c) => c.method === "mods.set_priority")?.params).toMatchObject({ name: "SourceMod", priority: 9 });
    expect(apply.result.target_mode).toBe("wins_over");
    expect(apply.result._meta).toEqual({
      priority_convention: "mobase_full_space_higher_wins",
      modlist_file_order: "reverse_of_gui",
      gui_direction_hint: "priority_0_at_gui_top_loses; priority_(N-1)_at_gui_bottom_wins",
    });
  });

  it("offline apply rewrites modlist without broker and returns GUI-aligned metadata", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    const plan = await _plan({ target_mode: "gui_bottom" }, ctx);

    const apply = await tool.handler({ mode: "apply", plan_id: plan.result.plan_id, lease_token: plan.result.lease_token }, ctx) as {
      ok: boolean;
      result: { source: string; new_priority: number; _meta: Record<string, string> };
    };

    expect(apply.ok).toBe(true);
    expect(apply.result.source).toBe("offline_modlist_reorder");
    expect(apply.result.new_priority).toBe(11);
    expect(apply.result._meta.priority_convention).toBe("mobase_full_space_higher_wins");
    const modlist = await readFile(join(root, "profiles", "Default", "modlist.txt"), "utf8");
    expect(modlist.split(/\r?\n/)[0]).toBe("+SourceMod");
  });

  it("throws when wins_over is missing anchor", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "wins_over" }, ctx)).rejects.toThrow(/wins_over_requires_anchor/);
  });

  it("throws when anchor is unknown", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "wins_over", anchor: "MissingMod" }, ctx)).rejects.toThrow(/anchor_not_found: MissingMod/);
  });

  it("throws when raw_priority is missing target_priority", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "raw_priority" }, ctx)).rejects.toThrow(/raw_priority_requires_target_priority_int/);
  });

  it("throws when conflict mode is used without sidecar", async () => {
    const { ctx } = await _fixture();

    await expect(_plan({ target_mode: "wins_over_conflicts" }, ctx)).rejects.toThrow(/sidecar_required_for_conflict_mode/);
  });

  it("rejects old mode names with invalid_arguments", async () => {
    const { ctx } = await _fixture();
    for (const oldMode of ["top", "bottom", "priority", "above_separator", "above_first_conflict", "below_last_conflict"]) {
      const result = await dispatchToolCall({
        toolName: "mo2_send_mod_to",
        rawArgs: { mode: "plan", name: "SourceMod", target_mode: oldMode },
        ctx,
        rules: [],
      });
      const env = JSON.parse(result.content[0].text) as { ok: boolean; error: { code: string; field_errors: Record<string, string[]> } };

      expect(result.isError).toBe(true);
      expect(env.ok).toBe(false);
      expect(env.error.code).toBe("invalid_arguments");
      expect(env.error.field_errors.target_mode.join("\n")).toContain("gui_top");
    }
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
