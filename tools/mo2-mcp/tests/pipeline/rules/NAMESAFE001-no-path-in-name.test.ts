import { describe, expect, it } from "vitest";
import { runRules, hasBlocking } from "../../../src/pipeline/rules.js";
import { pathTraversalDenyRule } from "../../../src/pipeline/rules/PATHSAFE001-path-traversal-deny.js";
import { nameSafetyDenyRule } from "../../../src/pipeline/rules/NAMESAFE001-no-path-in-name.js";
import { AuditLogger } from "../../../src/audit.js";
import { PlanCache } from "../../../src/plan-apply.js";
import { SnapshotManager } from "../../../src/snapshot.js";
import type { RuleFinding, ToolContext } from "../../../src/types.js";

const stubCtx = {
  config: {
    mo2Root: "/tmp",
    permissionCeiling: "metadata-editable" as const,
    allowedProfiles: ["Default"],
    deny: [],
    snapshotRoot: "/tmp/.mo2-mcp/snapshots",
    auditRoot: "/tmp/.mo2-mcp/audit",
  },
  sessionId: "test-session",
  plans: new PlanCache(),
  snapshots: new SnapshotManager("/tmp/.mo2-mcp/snapshots", "test-session"),
  audit: new AuditLogger("/tmp/.mo2-mcp/audit", "test-session"),
} satisfies ToolContext;

async function findingsForCreateModName(name: string): Promise<RuleFinding[]> {
  return runRules(
    [pathTraversalDenyRule, nameSafetyDenyRule],
    "mo2_create_mod",
    stubCtx,
    { mode: "plan", name },
  );
}

function firstBlocking(findings: RuleFinding[]): RuleFinding | undefined {
  expect(hasBlocking(findings)).toBe(true);
  return findings.find((finding) => finding.decision === "block");
}

describe("NAMESAFE001 no-path-in-name rule taxonomy", () => {
  it.each([
    "../escape",
    "..\\escape",
    "foo/../escape",
    "C:\\evil",
  ])("classifies unsafe mod name %s as NAMESAFE001", async (name) => {
    const findings = await findingsForCreateModName(name);

    expect(firstBlocking(findings)?.code).toBe("NAMESAFE001");
  });

  it("does not flag normal mod names", async () => {
    const findings = await findingsForCreateModName("normal_mod_name");

    expect(findings).toEqual([]);
  });
});
