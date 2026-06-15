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
  const root = await mkdtemp(join(tmpdir(), "mo2-snm-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods", "ModA"), { recursive: true });
  await writeFile(
    join(root, "mods", "ModA", "meta.ini"),
    "[General]\nversion=1.0\n",
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

describe("mo2_set_mod_notes", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-set-mod-notes.js");
  });

  it("registers as T2", () => {
    expect(getTool("mo2_set_mod_notes")?.tier).toBe("T2");
  });

  it("plan returns plan_id + lease_token + diff", async () => {
    const { ctx } = await _fixture();
    const tool = getTool("mo2_set_mod_notes")!;
    const result = (await tool.handler(
      { mode: "plan", name: "ModA", notes: "hello world" },
      ctx,
    )) as { ok: boolean; result: { planId?: string; lease_token?: string; diff?: string } };
    expect(result.ok).toBe(true);
    expect(result.result.planId).toBeDefined();
    expect(result.result.lease_token).toBeDefined();
    expect(result.result.diff).toContain("notes");
  });

  it("plan → apply round trip writes notes to meta.ini (offline)", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_set_mod_notes")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "ModA", notes: "my note" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const meta = await readFile(join(root, "mods", "ModA", "meta.ini"), "utf8");
    expect(meta).toContain('notes="my note"');
    expect(meta).toContain("version=1.0"); // existing field preserved
  });

  it("apply with mutated meta returns lease_violation", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_set_mod_notes")!;
    const plan = (await tool.handler(
      { mode: "plan", name: "ModA", notes: "x" },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };

    // External mutation
    await writeFile(
      join(root, "mods", "ModA", "meta.ini"),
      "[General]\nversion=999\n",
      "utf8",
    );

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean; error?: { code: string } };
    expect(apply.ok).toBe(false);
    expect(apply.error?.code).toBe("lease_violation");
  });
});
