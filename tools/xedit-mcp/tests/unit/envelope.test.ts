import { describe, it, expect } from "vitest";
import { ok, refuse, fromRuleFinding } from "../../src/envelope.js";

describe("envelope shaper", () => {
  it("ok() builds a minimal success envelope with empty warnings", () => {
    const e = ok({ tool: "xedit_session", summary: "ready" });
    expect(e.ok).toBe(true);
    expect(e.tool).toBe("xedit_session");
    expect(e.warnings).toEqual([]);
  });

  it("ok() passes through data and status", () => {
    const e = ok({
      tool: "xedit_read_record",
      summary: "1 record",
      data: { formId: "0x012345" },
      status: "completed",
    });
    if (!e.ok) throw new Error("expected ok");
    expect(e.data).toEqual({ formId: "0x012345" });
    expect(e.status).toBe("completed");
  });

  it("ok() default empty-warnings is not clobbered by input.warnings === undefined", () => {
    // Regression guard: an earlier version put the spread AFTER the default,
    // so an explicit-undefined warnings (which is allowed by the optional type)
    // would override the default [] with undefined.
    const e = ok({ tool: "x", summary: "s", warnings: undefined });
    expect(e.warnings).toEqual([]);
  });

  it("refuse() builds a refusal envelope with code + hint", () => {
    const e = refuse({
      tool: "xedit_find_record",
      summary: "blocked",
      code: "state_violation",
      hint: "load the file first",
    });
    expect(e.ok).toBe(false);
    if (e.ok) throw new Error("expected refusal");
    expect(e.code).toBe("state_violation");
    expect(e.hint).toBe("load the file first");
  });

  it("fromRuleFinding() maps a rule + finding to a rule_<id> refusal with status:refused", () => {
    const e = fromRuleFinding(
      { tool: "xedit_find_record" },
      {
        id: "LOAD001",
        appliesTo: ["xedit_find_record"],
        riskLevel: "CRITICAL",
        description: "Target not in load order",
        suggestion: "add to plugins.txt first",
        check: () => null,
      },
      { ruleId: "LOAD001", matched: { file: "X.esp" }, message: "not loaded" },
    );
    if (e.ok) throw new Error("expected refusal");
    expect(e.code).toBe("rule_LOAD001");
    expect(e.severity).toBe("CRITICAL");
    expect(e.hint).toBe("add to plugins.txt first");
    expect(e.matched).toEqual({ file: "X.esp" });
    expect(e.status).toBe("refused");
  });
});
