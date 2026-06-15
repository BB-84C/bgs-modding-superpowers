import { describe, expect, it } from "vitest";
import { runRules } from "../../src/pipeline/rules.js";
import { pathTraversalDenyRule } from "../../src/pipeline/rules/PATHSAFE001-path-traversal-deny.js";
import { AuditLogger } from "../../src/audit.js";
import { PlanCache } from "../../src/plan-apply.js";
import { SnapshotManager } from "../../src/snapshot.js";
import type { ToolContext } from "../../src/types.js";

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

async function findingsFor(args: Record<string, unknown>) {
  return runRules([pathTraversalDenyRule], "mo2_install", stubCtx, args);
}

describe("PATHSAFE001 path-traversal-deny", () => {
  it("rejects parent traversal in Windows archive paths", async () => {
    const findings = await findingsFor({ archive_path: "C:\\downloads\\..\\..\\evil.7z" });

    expect(findings[0]?.code).toBe("PATHSAFE001");
    expect(findings[0]?.decision).toBe("block");
  });

  it("rejects parent traversal in POSIX-style target paths", async () => {
    const findings = await findingsFor({ target_path: "subdir/../escape" });

    expect(findings[0]?.code).toBe("PATHSAFE001");
  });

  it("accepts legitimate archive paths without traversal segments", async () => {
    const findings = await findingsFor({ archive_path: "C:\\downloads\\good.7z" });

    expect(findings).toEqual([]);
  });

  it("rejects NUL bytes in any nested string", async () => {
    const findings = await findingsFor({ choices: [{ path: "safe\u0000evil" }] });

    expect(findings[0]?.code).toBe("PATHSAFE001");
  });
});
