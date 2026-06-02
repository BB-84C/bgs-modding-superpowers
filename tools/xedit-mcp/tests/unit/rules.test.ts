import { describe, it, expect } from "vitest";
import { createRegistry } from "../../src/rules/registry.js";
import { runRules } from "../../src/pipeline/rules.js";
import type { Rule, ToolContext } from "../../src/types.js";

const highRule: Rule = {
  id: "TEST001",
  appliesTo: ["xedit_x"],
  riskLevel: "HIGH",
  description: "test high",
  suggestion: "fix it",
  check: ({ args }) => (args.bad ? { ruleId: "TEST001", matched: {}, message: "bad" } : null),
};

const mediumRule: Rule = {
  id: "TEST002",
  appliesTo: ["xedit_x"],
  riskLevel: "MEDIUM",
  description: "test medium",
  suggestion: "consider",
  check: ({ args }) => (args.notable ? { ruleId: "TEST002", matched: {}, message: "notable" } : null),
};

const criticalRule: Rule = {
  id: "TEST003",
  appliesTo: ["xedit_x"],
  riskLevel: "CRITICAL",
  description: "test critical",
  suggestion: "stop",
  check: ({ args }) => (args.stop ? { ruleId: "TEST003", matched: {}, message: "halt" } : null),
};

const ctx: ToolContext = {
  sessionId: "s",
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("pipeline.rules", () => {
  it("registry returns rules for a matching tool only", () => {
    const reg = createRegistry([highRule]);
    expect(reg.forTool("xedit_x")).toHaveLength(1);
    expect(reg.forTool("xedit_y")).toHaveLength(0);
  });

  it("runRules returns no refusal and no warnings when nothing trips", async () => {
    const reg = createRegistry([highRule]);
    const r = await runRules({ tool: "xedit_x", args: {}, ctx, registry: reg });
    expect(r.refusal).toBeNull();
    expect(r.warnings).toEqual([]);
    expect(r.ruleHits).toEqual([]);
  });

  it("runRules returns a refusal envelope when a CRITICAL/HIGH rule trips", async () => {
    const reg = createRegistry([highRule]);
    const r = await runRules({ tool: "xedit_x", args: { bad: true }, ctx, registry: reg });
    expect(r.refusal).not.toBeNull();
    if (!r.refusal) throw new Error("expected refusal");
    expect(r.refusal.code).toBe("rule_TEST001");
    expect(r.refusal.severity).toBe("HIGH");
    expect(r.ruleHits).toEqual(["TEST001"]);
  });

  it("MEDIUM findings surface as warnings, not refusal (carry-forward #4)", async () => {
    const reg = createRegistry([mediumRule]);
    const r = await runRules({ tool: "xedit_x", args: { notable: true }, ctx, registry: reg });
    expect(r.refusal).toBeNull();
    expect(r.warnings).toHaveLength(1);
    expect(r.warnings[0]?.code).toBe("rule_TEST002");
    expect(r.warnings[0]?.severity).toBe("MEDIUM");
    expect(r.warnings[0]?.message).toContain("notable");
    expect(r.ruleHits).toEqual(["TEST002"]);
  });

  it("HIGH downgrades to warning when blockHigh=false", async () => {
    const reg = createRegistry([highRule]);
    const r = await runRules({
      tool: "xedit_x",
      args: { bad: true },
      ctx,
      registry: reg,
      blockHigh: false,
    });
    expect(r.refusal).toBeNull();
    expect(r.warnings).toHaveLength(1);
    expect(r.warnings[0]?.severity).toBe("HIGH");
  });

  it("CRITICAL always blocks; warnings collected before the blocker are returned", async () => {
    const reg = createRegistry([mediumRule, criticalRule]);
    const r = await runRules({
      tool: "xedit_x",
      args: { notable: true, stop: true },
      ctx,
      registry: reg,
    });
    expect(r.refusal).not.toBeNull();
    if (!r.refusal) throw new Error("expected refusal");
    expect(r.refusal.code).toBe("rule_TEST003");
    // The MEDIUM ran before the CRITICAL and is still in the warnings bag for the caller.
    expect(r.warnings).toHaveLength(1);
    expect(r.warnings[0]?.code).toBe("rule_TEST002");
    expect(r.ruleHits).toEqual(["TEST002", "TEST003"]);
  });
});
