import { describe, it, expect } from "vitest";
import { createRegistry } from "../../src/rules/registry.js";
import { runRules } from "../../src/pipeline/rules.js";
import type { Rule, ToolContext } from "../../src/types.js";

const exampleRule: Rule = {
  id: "TEST001",
  appliesTo: ["xedit_x"],
  riskLevel: "HIGH",
  description: "test",
  suggestion: "fix it",
  check: ({ args }) => (args.bad ? { ruleId: "TEST001", matched: {}, message: "bad" } : null),
};

const ctx: ToolContext = {
  sessionId: "s",
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("pipeline.rules", () => {
  it("registry returns rules for a matching tool only", () => {
    const reg = createRegistry([exampleRule]);
    expect(reg.forTool("xedit_x")).toHaveLength(1);
    expect(reg.forTool("xedit_y")).toHaveLength(0);
  });

  it("runRules returns null when nothing trips", async () => {
    const reg = createRegistry([exampleRule]);
    const r = await runRules({ tool: "xedit_x", args: {}, ctx, registry: reg });
    expect(r).toBeNull();
  });

  it("runRules returns a refusal envelope when a CRITICAL/HIGH rule trips", async () => {
    const reg = createRegistry([exampleRule]);
    const r = await runRules({ tool: "xedit_x", args: { bad: true }, ctx, registry: reg });
    expect(r).not.toBeNull();
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("rule_TEST001");
    expect(r.severity).toBe("HIGH");
  });
});
