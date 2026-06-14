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
  const root = await mkdtemp(join(tmpdir(), "mo2-sf-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "profiles", "Default", "modlist.txt"),
    "+ModA\n+ModB\n",
    "utf8",
  );
  await writeFile(join(root, "profiles", "Default", "plugins.txt"), "", "utf8");
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  const modsDir = join(root, "mods");
  await mkdir(join(modsDir, "ModA", "Data"), { recursive: true });
  await writeFile(join(modsDir, "ModA", "Data", "foo.esp"), "", "utf8");
  await writeFile(join(modsDir, "ModA", "Data", "bar.esm"), "", "utf8");
  await mkdir(join(modsDir, "ModB"), { recursive: true });
  await writeFile(join(modsDir, "ModB", "baz.esp"), "", "utf8");

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

describe("mo2_search_files", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-search-files.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_search_files")?.tier).toBe("T1");
  });

  it("finds .esp via glob", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_search_files")!;
    const result = (await tool.handler({ pattern: "**/*.esp", max_results: 100 }, ctx)) as {
      ok: boolean;
      result: { results: string[]; truncated: boolean };
    };
    expect(result.ok).toBe(true);
    expect(result.result.results).toContain("ModA/Data/foo.esp");
    expect(result.result.results).toContain("ModB/baz.esp");
    expect(result.result.results.some((r) => r.endsWith(".esm"))).toBe(false);
  });

  it("regex prefix matches", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_search_files")!;
    const result = (await tool.handler({ pattern: "regex:bar\\.esm$", max_results: 10 }, ctx)) as {
      ok: boolean;
      result: { results: string[] };
    };
    expect(result.ok).toBe(true);
    expect(result.result.results).toContain("ModA/Data/bar.esm");
  });

  it("respects max_results with truncated flag", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_search_files")!;
    const result = (await tool.handler({ pattern: "**/*.*", max_results: 1 }, ctx)) as {
      ok: boolean;
      result: { results: string[]; truncated: boolean };
    };
    expect(result.ok).toBe(true);
    expect(result.result.results).toHaveLength(1);
    expect(result.result.truncated).toBe(true);
  });
});
