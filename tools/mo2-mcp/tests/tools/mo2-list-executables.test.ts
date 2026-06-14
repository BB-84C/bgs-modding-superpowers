import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _fixture(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-le-"));
  await writeFile(
    join(root, "ModOrganizer.ini"),
    `[General]
game=fallout4
[Settings]
base_directory=${root}
[customExecutables]
size=2
1\\title=xEdit
1\\binary=C:/Tools/xEdit/xEdit.exe
1\\arguments=-fo4
1\\workingDirectory=
1\\steamAppID=
1\\ownicon=true
1\\hide=false
2\\title=LOOT
2\\binary=C:/LOOT/LOOT.exe
2\\arguments=
2\\workingDirectory=
2\\steamAppID=
2\\ownicon=false
2\\hide=false
`,
    "utf8",
  );

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

describe("mo2_list_executables", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-list-executables.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_list_executables")?.tier).toBe("T1");
  });

  it("returns 2 executables", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_list_executables")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { count: number; executables: Array<{ title: string; binary: string }> };
    };
    expect(result.ok).toBe(true);
    expect(result.result.count).toBe(2);
    expect(result.result.executables[0].title).toBe("xEdit");
    expect(result.result.executables[1].title).toBe("LOOT");
  });
});
