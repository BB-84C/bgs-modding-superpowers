import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-mi-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  const modsDir = join(root, "mods");
  const modAPath = join(modsDir, "ModA");
  await mkdir(modAPath, { recursive: true });
  await writeFile(
    join(modAPath, "meta.ini"),
    "[General]\nversion=1.0.0\nnotes=\"hello\"\n[Nexus]\nnexusID=42\n",
    "utf8",
  );
  await writeFile(join(modAPath, "textures.ba2"), "", "utf8");
  await mkdir(join(modAPath, "Data"));
  await writeFile(join(modAPath, "Data", "foo.esp"), "", "utf8");

  return {
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
}

describe("mo2_mod_info", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-mod-info.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_mod_info")?.tier).toBe("T1");
  });

  it("returns mod_not_found for nonexistent mod", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_mod_info")!;
    const result = (await tool.handler({ name: "NoSuch" }, ctx)) as {
      ok: boolean;
      error?: { code: string };
    };
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("mod_not_found");
  });

  it("returns meta.ini sections + counts", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_mod_info")!;
    const result = (await tool.handler({ name: "ModA" }, ctx)) as {
      ok: boolean;
      result: {
        meta: Record<string, Record<string, string>>;
        file_count: number;
        archive_count: number;
      };
    };
    expect(result.ok).toBe(true);
    expect(result.result.meta.General.version).toBe("1.0.0");
    expect(result.result.meta.Nexus.nexusID).toBe("42");
    expect(result.result.file_count).toBe(3); // meta.ini + textures.ba2 + Data/foo.esp
    expect(result.result.archive_count).toBe(1);
  });
});
