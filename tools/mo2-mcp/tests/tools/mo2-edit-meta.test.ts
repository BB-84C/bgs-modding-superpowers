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
  const root = await mkdtemp(join(tmpdir(), "mo2-em-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await mkdir(join(root, "mods", "ModA"), { recursive: true });
  await writeFile(join(root, "mods", "ModA", "meta.ini"), "[General]\nversion=1.0\n", "utf8");
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

describe("mo2_edit_meta", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-edit-meta.js");
  });

  it("registers as T2", () => {
    expect(getTool("mo2_edit_meta")?.tier).toBe("T2");
  });

  it("plan → apply edits multiple sections", async () => {
    const { root, ctx } = await _fixture();
    const tool = getTool("mo2_edit_meta")!;
    const plan = (await tool.handler(
      {
        mode: "plan",
        name: "ModA",
        updates: { General: { version: "2.0" }, Nexus: { nexusID: "42" } },
      },
      ctx,
    )) as { ok: boolean; result: { planId: string; lease_token: string } };
    expect(plan.ok).toBe(true);

    const apply = (await tool.handler(
      { mode: "apply", plan_id: plan.result.planId, lease_token: plan.result.lease_token },
      ctx,
    )) as { ok: boolean };
    expect(apply.ok).toBe(true);

    const meta = await readFile(join(root, "mods", "ModA", "meta.ini"), "utf8");
    expect(meta).toContain("version=2.0");
    expect(meta).toContain("nexusID=42");
  });
});
