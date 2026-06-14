import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _setupMo2Root(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "mo2-status-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "+ModA\n-ModB\n", "utf8");
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "*Fallout4.esm\n", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\ngameName=Fallout 4\ngamePath=C:/Games/FO4\n[Settings]\nbase_directory=" +
      root +
      "\n",
    "utf8",
  );
  return root;
}

function _buildCtx(mo2Root: string): ToolContext {
  return {
    config: {
      mo2Root,
      permissionCeiling: "metadata-editable",
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(mo2Root, ".mo2-mcp", "snapshots"),
      auditRoot: join(mo2Root, ".mo2-mcp", "audit"),
    },
    sessionId: "test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(mo2Root, ".mo2-mcp", "snapshots"), "test"),
    audit: new AuditLogger(join(mo2Root, ".mo2-mcp", "audit"), "test"),
  };
}

describe("mo2_status", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-status.js");
  });

  it("registers as T1 tool", () => {
    const tool = getTool("mo2_status");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns instance state with counts", async () => {
    const mo2Root = await _setupMo2Root();
    const ctx = _buildCtx(mo2Root);
    const tool = getTool("mo2_status")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: {
        mo2_root: string;
        game?: string;
        permission_ceiling: string;
        counts: { mods_total: number; mods_enabled: number; plugins_total: number; plugins_enabled: number } | null;
        detection: { online: boolean };
      };
    };
    expect(result.ok).toBe(true);
    expect(result.result.mo2_root).toBe(mo2Root);
    expect(result.result.game).toBe("fallout4");
    expect(result.result.permission_ceiling).toBe("metadata-editable");
    expect(result.result.counts?.mods_total).toBe(2);
    expect(result.result.counts?.mods_enabled).toBe(1);
    expect(result.result.counts?.plugins_enabled).toBe(1);
  });
});
