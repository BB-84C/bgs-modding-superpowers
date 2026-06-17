import { beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";
import { AuditLogger } from "../../../src/audit.js";
import { permissionCeilingRule } from "../../../src/pipeline/rules/CEILING001-permission-ceiling.js";
import { hasBlocking, runRules } from "../../../src/pipeline/rules.js";
import { PlanCache } from "../../../src/plan-apply.js";
import { SnapshotManager } from "../../../src/snapshot.js";
import { _clearToolsForTests, registerTool } from "../../../src/tool-registry.js";
import type { Config } from "../../../src/config.js";
import type { ToolContext } from "../../../src/types.js";

type PermissionCeiling = Config["permissionCeiling"];
type ToolTier = "T1" | "T2" | "T3";

const EMPTY_SCHEMA = z.object({});

const REPRESENTATIVE_TOOLS: Array<{
  name: string;
  tier: ToolTier;
  args: Record<string, unknown>;
  requiredCeiling: PermissionCeiling;
  allowedCeilings: PermissionCeiling[];
}> = [
  {
    name: "mo2_modlist",
    tier: "T1",
    args: { profile: "Default" },
    requiredCeiling: "read-only",
    allowedCeilings: ["read-only", "metadata-editable", "full-control"],
  },
  {
    name: "mo2_set_mod_notes",
    tier: "T2",
    args: { mode: "plan", name: "Example Mod", notes: "test note" },
    requiredCeiling: "metadata-editable",
    allowedCeilings: ["metadata-editable", "full-control"],
  },
  {
    name: "mo2_toggle_mod",
    tier: "T3",
    args: { mode: "plan", name: "Example Mod", enabled: true, profile: "Default" },
    requiredCeiling: "full-control",
    allowedCeilings: ["full-control"],
  },
];

const CEILINGS: PermissionCeiling[] = ["read-only", "metadata-editable", "full-control"];

function ctx(permissionCeiling: PermissionCeiling): ToolContext {
  return {
    config: {
      mo2Root: "/tmp/mo2",
      permissionCeiling,
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: "/tmp/mo2/.mo2-mcp/snapshots",
      auditRoot: "/tmp/mo2/.mo2-mcp/audit",
    },
    sessionId: "ceiling001-readonly-direction-test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager("/tmp/mo2/.mo2-mcp/snapshots", "ceiling001-readonly-direction-test"),
    audit: new AuditLogger("/tmp/mo2/.mo2-mcp/audit", "ceiling001-readonly-direction-test"),
  };
}

function registerRepresentativeTools(): void {
  for (const tool of REPRESENTATIVE_TOOLS) {
    registerTool({
      name: tool.name,
      tier: tool.tier,
      description: `Representative ${tool.tier} CEILING001 test tool`,
      inputSchema: EMPTY_SCHEMA,
      handler: async () => ({ ok: true, result: { invoked: tool.name }, error: null }),
    });
  }
}

describe("CEILING001 read-only direction", () => {
  beforeEach(() => {
    _clearToolsForTests();
    registerRepresentativeTools();
  });

  it.each(CEILINGS)("enforces representative T1/T2/T3 tools at ceiling %s", async (ceiling) => {
    for (const tool of REPRESENTATIVE_TOOLS) {
      const findings = await runRules([permissionCeilingRule], tool.name, ctx(ceiling), tool.args);
      const shouldAllow = tool.allowedCeilings.includes(ceiling);

      if (shouldAllow) {
        expect(findings, `${tool.name} should pass at ${ceiling}`).toEqual([]);
      } else {
        expect(hasBlocking(findings), `${tool.name} should be blocked at ${ceiling}`).toBe(true);
        expect(findings[0]).toMatchObject({
          code: "CEILING001",
          decision: "block",
          tier: tool.tier,
          required_ceiling: tool.requiredCeiling,
          configured_ceiling: ceiling,
        });
      }
    }
  });
});
