import { beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";
import { AuditLogger } from "../src/audit.js";
import { dispatchToolCall } from "../src/dispatch.js";
import { permissionCeilingRule } from "../src/pipeline/rules/CEILING001-permission-ceiling.js";
import { PlanCache } from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { _clearToolsForTests, registerTool } from "../src/tool-registry.js";
import type { Config } from "../src/config.js";
import type { ToolContext } from "../src/types.js";

const invoked: string[] = [];

function ctx(permissionCeiling: Config["permissionCeiling"]): ToolContext {
  return {
    config: {
      mo2Root: "/tmp/mo2",
      permissionCeiling,
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: "/tmp/mo2/.mo2-mcp/snapshots",
      auditRoot: "/tmp/mo2/.mo2-mcp/audit",
    },
    sessionId: "dispatch-ceiling-test",
    plans: new PlanCache(),
    snapshots: new SnapshotManager("/tmp/mo2/.mo2-mcp/snapshots", "dispatch-ceiling-test"),
    audit: new AuditLogger("/tmp/mo2/.mo2-mcp/audit", "dispatch-ceiling-test"),
  };
}

function responseText(result: Awaited<ReturnType<typeof dispatchToolCall>>): any {
  return JSON.parse(result.content[0].text);
}

describe("dispatch CEILING001 integration", () => {
  beforeEach(() => {
    invoked.length = 0;
    _clearToolsForTests();
    for (const name of ["mo2_toggle_mod", "mo2_install", "mo2_rename_profile"]) {
      registerTool({
        name,
        description: "representative T3 test tool",
        tier: "T3",
        inputSchema: z.object({}),
        handler: async () => {
          invoked.push(name);
          return { ok: true, result: { invoked: name }, error: null };
        },
      });
    }
  });

  it("blocks representative T3 tools at metadata-editable before handlers run", async () => {
    for (const name of ["mo2_toggle_mod", "mo2_install", "mo2_rename_profile"]) {
      const result = await dispatchToolCall({
        toolName: name,
        rawArgs: {},
        ctx: ctx("metadata-editable"),
        rules: [permissionCeilingRule],
      });

      expect(responseText(result)).toMatchObject({
        ok: false,
        error: {
          code: "CEILING001",
          tier: "T3",
          configured_ceiling: "metadata-editable",
          required_ceiling: "full-control",
        },
      });
    }
    expect(invoked).toEqual([]);
  });

  it("allows representative T3 tools at full-control and invokes handlers", async () => {
    for (const name of ["mo2_toggle_mod", "mo2_install", "mo2_rename_profile"]) {
      const result = await dispatchToolCall({
        toolName: name,
        rawArgs: {},
        ctx: ctx("full-control"),
        rules: [permissionCeilingRule],
      });

      expect(responseText(result)).toMatchObject({ ok: true, result: { invoked: name } });
    }
    expect(invoked).toEqual(["mo2_toggle_mod", "mo2_install", "mo2_rename_profile"]);
  });
});
