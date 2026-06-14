import { describe, it, expect, beforeEach } from "vitest";
import { _clearRulesForTests, registerRule, getAllRules } from "../src/pipeline/registry.js";
import { runRules, hasBlocking } from "../src/pipeline/rules.js";
import { stockGameDenyRule } from "../src/pipeline/rules/STOCK001-stock-game-deny.js";
import type { Rule, ToolContext } from "../src/types.js";

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
} satisfies ToolContext;

describe("rule registry", () => {
  beforeEach(() => {
    _clearRulesForTests();
  });

  it("starts empty after clear", () => {
    expect(getAllRules()).toEqual([]);
  });

  it("registers and lists rules", () => {
    const dummy: Rule = {
      id: "TEST001",
      severity: "MEDIUM",
      appliesTo: () => true,
      evaluate: async () => null,
    };
    registerRule(dummy);
    expect(getAllRules()).toHaveLength(1);
    expect(getAllRules()[0].id).toBe("TEST001");
  });
});

describe("runRules", () => {
  beforeEach(() => {
    _clearRulesForTests();
  });

  it("returns empty findings when no rules registered", async () => {
    const findings = await runRules([], "mo2_status", stubCtx, {});
    expect(findings).toEqual([]);
  });

  it("collects findings from applicable rules only", async () => {
    const r1: Rule = {
      id: "R1",
      severity: "MEDIUM",
      appliesTo: (toolName) => toolName === "mo2_status",
      evaluate: async () => ({ code: "R1", severity: "MEDIUM", decision: "warn", message: "r1" }),
    };
    const r2: Rule = {
      id: "R2",
      severity: "HIGH",
      appliesTo: (toolName) => toolName === "other_tool",
      evaluate: async () => ({ code: "R2", severity: "HIGH", decision: "block", message: "r2" }),
    };

    const findings = await runRules([r1, r2], "mo2_status", stubCtx, {});
    expect(findings).toHaveLength(1);
    expect(findings[0].code).toBe("R1");
  });

  it("wraps rule throws as MEDIUM warnings", async () => {
    const bad: Rule = {
      id: "BAD",
      severity: "HIGH",
      appliesTo: () => true,
      evaluate: async () => {
        throw new Error("boom");
      },
    };
    const findings = await runRules([bad], "mo2_status", stubCtx, {});
    expect(findings[0].code).toBe("BAD-error");
    expect(findings[0].decision).toBe("warn");
    expect(findings[0].message).toContain("boom");
  });

  it("hasBlocking returns true when any finding is block", () => {
    expect(
      hasBlocking([
        { code: "X", severity: "MEDIUM", decision: "warn", message: "" },
        { code: "Y", severity: "CRITICAL", decision: "block", message: "" },
      ]),
    ).toBe(true);
    expect(hasBlocking([{ code: "X", severity: "MEDIUM", decision: "pass", message: "" }])).toBe(false);
  });
});

describe("STOCK001 stock-game-deny", () => {
  beforeEach(() => {
    _clearRulesForTests();
    registerRule(stockGameDenyRule);
  });

  it("blocks paths under Stock Game/Data", async () => {
    const rules = getAllRules();
    const findings = await runRules(rules, "mo2_set_mod_notes", stubCtx, {
      path: "C:/Games/MO2/Stock Game/Data/Fallout4.esm",
    });
    expect(findings).toHaveLength(1);
    expect(findings[0].code).toBe("STOCK001");
    expect(findings[0].decision).toBe("block");
  });

  it("blocks Stock Game/Data with backslashes (Windows)", async () => {
    const rules = getAllRules();
    const findings = await runRules(rules, "mo2_set_mod_notes", stubCtx, {
      virtual_path: "C:\\MO2\\Stock Game\\Data\\Skyrim.esm",
    });
    expect(findings[0].code).toBe("STOCK001");
  });

  it("allows mods/ paths through", async () => {
    const rules = getAllRules();
    const findings = await runRules(rules, "mo2_install", stubCtx, {
      archive_path: "C:/downloads/Foo.7z",
      path: "C:/MO2/mods/Foo/Data/foo.esp",
    });
    expect(findings).toEqual([]);
  });
});
