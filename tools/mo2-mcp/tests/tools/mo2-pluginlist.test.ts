import { describe, it, expect, beforeAll } from "vitest";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { getTool, _clearToolsForTests } from "../../src/tool-registry.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import { AuditLogger } from "../../src/audit.js";
import type { ToolContext } from "../../src/types.js";

async function _buildCtx(): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-pl-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(join(root, "profiles", "Default", "modlist.txt"), "", "utf8");
  await writeFile(
    join(root, "profiles", "Default", "plugins.txt"),
    "*Fallout4.esm\n*DLCRobot.esm\nDisabled.esp\n# comment line\n",
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

describe("mo2_pluginlist", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-pluginlist.js");
  });

  it("registers as T1", () => {
    const tool = getTool("mo2_pluginlist");
    expect(tool).toBeDefined();
    expect(tool!.tier).toBe("T1");
  });

  it("returns plugins with correct * polarity (* = enabled)", async () => {
    const ctx = await _buildCtx();
    const tool = getTool("mo2_pluginlist")!;
    const result = (await tool.handler({}, ctx)) as {
      ok: boolean;
      result: { plugins: Array<{ name: string; enabled: boolean; isComment?: boolean }> };
    };
    expect(result.ok).toBe(true);
    const plugins = result.result.plugins;
    expect(plugins).toHaveLength(4);
    expect(plugins[0]).toMatchObject({ name: "Fallout4.esm", enabled: true });
    expect(plugins[2]).toMatchObject({ name: "Disabled.esp", enabled: false });
    expect(plugins[3]).toMatchObject({ name: "comment line", enabled: false });
  });
});
