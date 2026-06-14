import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<{ root: string; ctx: ToolContext }> {
  const root = await mkdtemp(join(tmpdir(), "mo2-sm-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    "+TopMod\n+MiddleMod\n+MySection_separator\n+BottomMod\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
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

describe("mo2_send_mod_to", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-send-mod-to.js");
  });

  it("registers as T3", () => {
    expect(getTool("mo2_send_mod_to")?.tier).toBe("T3");
  });

  it("plan with target_mode=top returns highest priority", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "BottomMod", target_mode: "top" },
      ctx,
    )) as { ok: boolean; result: { diff: string } };
    expect(plan.ok).toBe(true);
    expect(plan.result.diff).toContain("BottomMod");
  });

  it("plan with target_mode=above_separator finds the separator", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        name: "BottomMod",
        target_mode: "above_separator",
        target_separator: "MySection_separator",
      },
      ctx,
    )) as { ok: boolean };
    expect(plan.ok).toBe(true);
  });

  it("plan with target_mode=above_separator unknown separator throws", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    await expect(
      tool.handler(
        {
          mode: "plan",
          name: "BottomMod",
          target_mode: "above_separator",
          target_separator: "NoSuch_separator",
        },
        ctx,
      ),
    ).rejects.toThrow(/separator_not_found/);
  });

  it("conflict modes throw without sidecar", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_send_mod_to")!;
    await expect(
      tool.handler(
        { mode: "plan", name: "BottomMod", target_mode: "above_first_conflict" },
        ctx,
      ),
    ).rejects.toThrow(/sidecar_required/);
  });
});
