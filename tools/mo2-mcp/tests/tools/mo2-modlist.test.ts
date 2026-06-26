import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(modlistText = "+TopMod\n+MyGroup_separator\n+MiddleMod\n-DisabledMod\n"): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-ml-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), modlistText, "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
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

describe("mo2_modlist", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-modlist.js");
  });

  it("registers as T1", () => {
    const tool = getTool("mo2_modlist");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns mods in GUI top-first order with correct polarity + priority inversion", async () => {
    const { ctx } = await _buildCtx();
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { mods: Array<{ name: string; enabled: boolean; is_separator: boolean; priority: number; gui_rank: number; wins_over_count: number; section: string | null }>; _meta: { array_order: string } };
    };
    expect(result.ok).toBe(true);
    const mods = result.result.mods;
    expect(mods).toHaveLength(4);
    expect(mods.map((m) => m.name)).toEqual(["DisabledMod", "MiddleMod", "MyGroup_separator", "TopMod"]);
    expect(mods[0]).toMatchObject({ name: "DisabledMod", enabled: false, is_separator: false, priority: 0 });
    expect(mods[2]).toMatchObject({ name: "MyGroup_separator", is_separator: true });
    expect(mods[3]).toMatchObject({ name: "TopMod", enabled: true, priority: 3 });
    expect(result.result._meta.array_order).toBe("gui_top_first");
    for (const mod of mods) {
      expect(mod.gui_rank).toBe(mod.priority + 1);
      expect(mod.wins_over_count).toBe(mod.priority);
    }
  });

  it("computes section from the closest separator below each mod priority", async () => {
    const { ctx } = await _buildCtx(
      [
        "+HighMod",
        "+High_separator",
        "+MidHighMod",
        "+MidLowMod",
        "+Mid_separator",
        "+LowMod",
        "+BaseMod",
      ].join("\n") + "\n",
    );
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({}, ctx)) as {
      result: { mods: Array<{ name: string; priority: number; section: string | null; is_separator: boolean }> };
    };
    const byName = new Map(result.result.mods.map((m) => [m.name, m]));

    expect(byName.get("BaseMod")).toMatchObject({ priority: 0, section: null });
    expect(byName.get("LowMod")).toMatchObject({ priority: 1, section: null });
    expect(byName.get("Mid_separator")).toMatchObject({ priority: 2, section: null, is_separator: true });
    expect(byName.get("MidLowMod")).toMatchObject({ priority: 3, section: "Mid_separator" });
    expect(byName.get("MidHighMod")).toMatchObject({ priority: 4, section: "Mid_separator" });
    expect(byName.get("High_separator")).toMatchObject({ priority: 5, section: null, is_separator: true });
    expect(byName.get("HighMod")).toMatchObject({ priority: 6, section: "High_separator" });
  });

  it("mirrors BB84 separator semantics including Real Fuel between two separators", async () => {
    const { ctx } = await _buildCtx(
      [
        "+版本已过期_separator",
        "+Deprecated Ship Tweaks",
        "+Real Fuel - BETA",
        "+Fuel Economy Patch",
        "+Old Quest Patch",
        "+Ship Vendor Notes",
        "+观望_separator",
        "+Maybe Later Framework",
        "+Ambient Audio Lite",
        "+低风险_separator",
        "+Base Texture Tweak",
      ].join("\n") + "\n",
    );
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({}, ctx)) as {
      result: { mods: Array<{ name: string; priority: number; section: string | null; is_separator: boolean; gui_rank: number }> };
    };
    const byName = new Map(result.result.mods.map((m) => [m.name, m]));

    expect(result.result.mods.map((m) => m.priority)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(byName.get("Base Texture Tweak")).toMatchObject({ priority: 0, section: null, gui_rank: 1 });
    expect(byName.get("Ambient Audio Lite")).toMatchObject({ priority: 2, section: "低风险_separator" });
    expect(byName.get("Maybe Later Framework")).toMatchObject({ priority: 3, section: "低风险_separator" });
    expect(byName.get("Real Fuel - BETA")).toMatchObject({ priority: 8, section: "观望_separator" });
    expect(byName.get("Deprecated Ship Tweaks")).toMatchObject({ priority: 9, section: "观望_separator" });
    expect(byName.get("版本已过期_separator")).toMatchObject({ priority: 10, section: null, is_separator: true });
  });

  it("enrich=true is silently no-op without pipeClient", async () => {
    const { ctx } = await _buildCtx();
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({ enrich: true }, ctx)) as { ok: boolean };
    expect(result.ok).toBe(true);
  });
});
