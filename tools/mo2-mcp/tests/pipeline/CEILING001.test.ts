import { describe, expect, it, beforeEach } from "vitest";
import { z } from "zod";
import { runRules } from "../../src/pipeline/rules.js";
import { permissionCeilingRule } from "../../src/pipeline/rules/CEILING001-permission-ceiling.js";
import { _clearToolsForTests, registerTool } from "../../src/tool-registry.js";
import { AuditLogger } from "../../src/audit.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import type { Config } from "../../src/config.js";
import type { ToolContext } from "../../src/types.js";

const schema = z.object({});

function ctx(ceiling: Config["permissionCeiling"]): ToolContext {
  return {
    config: {
      mo2Root: "/tmp",
      permissionCeiling: ceiling,
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: "/tmp/.mo2-mcp/snapshots",
      auditRoot: "/tmp/.mo2-mcp/audit",
    },
    sessionId: "test-session",
    plans: new PlanCache(),
    snapshots: new SnapshotManager("/tmp/.mo2-mcp/snapshots", "test-session"),
    audit: new AuditLogger("/tmp/.mo2-mcp/audit", "test-session"),
  };
}

function registerTieredTools(): void {
  registerTool({ name: "mock_t1", tier: "T1", description: "read", inputSchema: schema, handler: async () => ({}) });
  registerTool({ name: "mock_t2", tier: "T2", description: "metadata", inputSchema: schema, handler: async () => ({}) });
  registerTool({ name: "mock_t3", tier: "T3", description: "mutate", inputSchema: schema, handler: async () => ({}) });
}

async function findings(toolName: string, ceiling: Config["permissionCeiling"]) {
  return runRules([permissionCeilingRule], toolName, ctx(ceiling), {});
}

describe("CEILING001 permission ceiling", () => {
  beforeEach(() => {
    _clearToolsForTests();
    registerTieredTools();
  });

  it("allows T1 tools under every ceiling", async () => {
    await expect(findings("mock_t1", "read-only")).resolves.toEqual([]);
    await expect(findings("mock_t1", "metadata-editable")).resolves.toEqual([]);
    await expect(findings("mock_t1", "full-control")).resolves.toEqual([]);
  });

  it("refuses T2 tools under read-only", async () => {
    const out = await findings("mock_t2", "read-only");
    expect(out[0]).toMatchObject({
      code: "CEILING001",
      decision: "block",
      tier: "T2",
      required_ceiling: "metadata-editable",
      configured_ceiling: "read-only",
    });
  });

  it("allows T2 tools under metadata-editable and full-control", async () => {
    await expect(findings("mock_t2", "metadata-editable")).resolves.toEqual([]);
    await expect(findings("mock_t2", "full-control")).resolves.toEqual([]);
  });

  it("refuses T3 tools under read-only and metadata-editable", async () => {
    const readOnly = await findings("mock_t3", "read-only");
    expect(readOnly[0]).toMatchObject({
      code: "CEILING001",
      decision: "block",
      tier: "T3",
      required_ceiling: "full-control",
      configured_ceiling: "read-only",
    });

    const metadataEditable = await findings("mock_t3", "metadata-editable");
    expect(metadataEditable[0]).toMatchObject({
      code: "CEILING001",
      decision: "block",
      tier: "T3",
      required_ceiling: "full-control",
      configured_ceiling: "metadata-editable",
    });
  });

  it("allows T3 tools under full-control", async () => {
    await expect(findings("mock_t3", "full-control")).resolves.toEqual([]);
  });
});
