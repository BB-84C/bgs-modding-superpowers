import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-ml-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    "+TopMod\n+MyGroup_separator\n+MiddleMod\n-DisabledMod\n",
    "utf8",
  );
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

  it("returns mods with correct polarity + priority inversion", async () => {
    const { ctx } = await _buildCtx();
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { mods: Array<{ name: string; enabled: boolean; is_separator: boolean; priority: number }> };
    };
    expect(result.ok).toBe(true);
    const mods = result.result.mods;
    expect(mods).toHaveLength(4);
    expect(mods[0]).toMatchObject({ name: "TopMod", enabled: true, is_separator: false, priority: 3 });
    expect(mods[1]).toMatchObject({ name: "MyGroup_separator", is_separator: true });
    expect(mods[3]).toMatchObject({ name: "DisabledMod", enabled: false, priority: 0 });
  });

  it("enrich=true is silently no-op without pipeClient", async () => {
    const { ctx } = await _buildCtx();
    const tool = getTool("mo2_modlist")!;
    const result = (await tool.handler({ enrich: true }, ctx)) as { ok: boolean };
    expect(result.ok).toBe(true);
  });
});
