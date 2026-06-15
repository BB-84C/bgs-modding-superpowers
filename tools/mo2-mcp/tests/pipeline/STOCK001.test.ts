import { describe, expect, it } from "vitest";
import { runRules } from "../../src/pipeline/rules.js";
import { stockGameDenyRule } from "../../src/pipeline/rules/STOCK001-stock-game-deny.js";
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
  return runRules([stockGameDenyRule], "mo2_install", stubCtx, args);
}

describe("STOCK001 stock-game-deny", () => {
  it("catches Fallout 4 Stock Game/Data paths", async () => {
    const findings = await findingsFor({
      target_path: "C:/MO2/Stock Game/Fallout 4/Data/Fallout4.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
    expect(findings[0]?.decision).toBe("block");
  });

  it("catches Fallout 4 Data root without a trailing slash", async () => {
    const findings = await findingsFor({
      target_path: "C:/MO2/Stock Game/Fallout 4/Data",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Fallout 4 Stock Game/Data paths with Windows backslashes", async () => {
    const findings = await findingsFor({
      target_path: "C:\\MO2\\Stock Game\\Fallout 4\\Data\\Fallout4.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Fallout 4 Windows Data root without a trailing backslash", async () => {
    const findings = await findingsFor({
      target_path: "C:\\MO2\\Stock Game\\Fallout 4\\Data",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Stock Game/Data without game folder or trailing slash", async () => {
    const findings = await findingsFor({ path: "Stock Game\\Data" });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Skyrim Special Edition Stock Game/Data paths", async () => {
    const findings = await findingsFor({
      path: "C:/MO2/Stock Game/Skyrim Special Edition/Data/Skyrim.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Skyrim Special Edition Data root with a trailing slash", async () => {
    const findings = await findingsFor({
      path: "Stock Game/Skyrim Special Edition/Data/",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Starfield Stock Game/Data paths", async () => {
    const findings = await findingsFor({
      archive_path: "C:/MO2/Stock Game/Starfield/Data/Starfield.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Fallout New Vegas Stock Game/Data paths", async () => {
    const findings = await findingsFor({
      path: "C:/MO2/Stock Game/Fallout New Vegas/Data/FalloutNV.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Stock Game path nested inside plan args", async () => {
    const findings = await findingsFor({
      mode: "plan",
      target_path: "C:/MO2/Stock Game/Fallout 4/Data/Fallout4.esm",
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("catches Stock Game path in deeply nested args", async () => {
    const findings = await findingsFor({
      mode: "plan",
      choices: [{ path: "C:/MO2/Stock Game/Fallout 4/Data/evil.esp" }],
    });

    expect(findings[0]?.code).toBe("STOCK001");
  });

  it("does not block bare plugin names without a Stock Game prefix", async () => {
    const findings = await findingsFor({ path: "Fallout4.esm" });

    expect(findings).toEqual([]);
  });

  it("does not block non-Stock Game paths with Game/Data text", async () => {
    const findings = await findingsFor({ path: "My Mod Game/Data" });

    expect(findings).toEqual([]);
  });

  it("does not block Stock Game paths that do not include a Data segment", async () => {
    const findings = await findingsFor({ path: "Stock Game/screenshots/something.png" });

    expect(findings).toEqual([]);
  });
});
