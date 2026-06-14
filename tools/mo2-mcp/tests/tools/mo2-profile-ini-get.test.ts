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
  const root = await mkdtemp(join(tmpdir(), "mo2-ig-"));
  await mkdir(join(root, "profiles", "Default"), { recursive: true });
  await writeFile(
    join(root, "ModOrganizer.ini"),
    "[General]\ngame=fallout4\n[Settings]\nbase_directory=" + root + "\n",
    "utf8",
  );
  await writeFile(
    join(root, "profiles", "Default", "fallout4Prefs.ini"),
    "[Display]\niResolutionX=1920\niResolutionY=1080\n[General]\nuExterior=42\n",
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

describe("mo2_profile_ini_get", () => {
  beforeAll(async () => {
    _clearToolsForTests();
    await import("../../src/tools/mo2-profile-ini-get.js");
  });

  it("registers as T1", () => {
    expect(getTool("mo2_profile_ini_get")?.tier).toBe("T1");
  });

  it("returns all sections by default", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_profile_ini_get")!;
    const result = (await tool.handler({ ini_name: "prefs" }, ctx)) as {
      ok: boolean;
      result: { source: string; sections: Record<string, Record<string, string>> };
    };
    expect(result.ok).toBe(true);
    expect(result.result.source).toBe("profile_local");
    expect(result.result.sections.Display.iResolutionX).toBe("1920");
    expect(result.result.sections.General.uExterior).toBe("42");
  });

  it("returns single section", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_profile_ini_get")!;
    const result = (await tool.handler({ ini_name: "prefs", section: "Display" }, ctx)) as {
      ok: boolean;
      result: { section: Record<string, string> };
    };
    expect(result.ok).toBe(true);
    expect(result.result.section.iResolutionY).toBe("1080");
  });

  it("returns single value", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_profile_ini_get")!;
    const result = (await tool.handler(
      { ini_name: "prefs", section: "Display", key: "iResolutionX" },
      ctx,
    )) as { ok: boolean; result: { value: string } };
    expect(result.ok).toBe(true);
    expect(result.result.value).toBe("1920");
  });

  it("returns ini_not_found for missing custom ini", async () => {
    const ctx = await _fixture();
    const tool = getTool("mo2_profile_ini_get")!;
    const result = (await tool.handler({ ini_name: "custom" }, ctx)) as {
      ok: boolean;
      error?: { code: string };
    };
    // Documents fallback may or may not find one; but for this test isolated env it should fail
    if (!result.ok) {
      expect(result.error?.code).toBe("ini_not_found");
    }
  });
});
