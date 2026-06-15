import { describe, expect, it } from "vitest";
import { runRules } from "../../src/pipeline/rules.js";
import { nameSafetyDenyRule } from "../../src/pipeline/rules/NAMESAFE001-no-path-in-name.js";
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
  return runRules([nameSafetyDenyRule], "mo2_install", stubCtx, args);
}

describe("NAMESAFE001 no-path-in-name", () => {
  it("rejects parent traversal in name fields", async () => {
    const findings = await findingsFor({ name: "../escape" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
    expect(findings[0]?.decision).toBe("block");
  });

  it("rejects forward slashes in name fields", async () => {
    const findings = await findingsFor({ name: "mod/with/slash" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects backslashes and drive colon in profile fields", async () => {
    const findings = await findingsFor({ profile: "C:\\Windows" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects pipe characters in new_name fields", async () => {
    const findings = await findingsFor({ new_name: "name|with|pipe" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects asterisks in source fields", async () => {
    const findings = await findingsFor({ source: "mod*with*star" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects leading or trailing whitespace in name-shaped fields", async () => {
    const findings = await findingsFor({ old_name: " MyMod" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects control characters in name-shaped fields", async () => {
    const findings = await findingsFor({ target: "bad\u001fname" });

    expect(findings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects path syntax in mod_name fields", async () => {
    const slashFindings = await findingsFor({ mod_name: "bad/nested" });
    const traversalFindings = await findingsFor({ mod_name: "../escape" });

    expect(slashFindings[0]?.code).toBe("NAMESAFE001");
    expect(traversalFindings[0]?.code).toBe("NAMESAFE001");
  });

  it("rejects path syntax in audited name-shaped tool fields", async () => {
    const newProfileFindings = await findingsFor({ new_profile: "bad/nested" });
    const aboveFindings = await findingsFor({ above: "../Separator" });
    const targetSeparatorFindings = await findingsFor({ target_separator: "Bad\\Separator" });
    const labelFindings = await findingsFor({ label: "bad/backup" });

    expect(newProfileFindings[0]?.code).toBe("NAMESAFE001");
    expect(aboveFindings[0]?.code).toBe("NAMESAFE001");
    expect(targetSeparatorFindings[0]?.code).toBe("NAMESAFE001");
    expect(labelFindings[0]?.code).toBe("NAMESAFE001");
  });

  it("accepts legitimate name-shaped values", async () => {
    const findings = await findingsFor({
      name: "MyMod",
      mod_name: "Good Mod",
      profile: "Default",
      new_profile: "Profile B",
      above: "Separator One",
      target_separator: "Quest Mods",
      label: "before cleanup",
      title: "xEdit Automation Serve",
    });

    expect(findings).toEqual([]);
  });

  it("does not inspect path-shaped fields", async () => {
    const findings = await findingsFor({
      archive_path: "C:\\downloads\\good.7z",
      path: "textures/foo.dds",
      virtual_path: "meshes\\bar.nif",
    });

    expect(findings).toEqual([]);
  });
});
