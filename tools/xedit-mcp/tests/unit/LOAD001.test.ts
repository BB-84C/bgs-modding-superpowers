import { describe, it, expect } from "vitest";
import { LOAD001 } from "../../src/rules/LOAD001.js";
import type { ToolContext } from "../../src/types.js";

const ctx: ToolContext = {
  sessionId: "s",
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("rule LOAD001", () => {
  it("appliesTo includes the Batch 1 read tools", () => {
    expect(LOAD001.appliesTo).toEqual(
      expect.arrayContaining(["xedit_find_record", "xedit_read_record", "xedit_inspect_conflicts"]),
    );
  });

  it("returns null when target file is loaded", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: { file: "Patch.esp" }, ctx });
    expect(f).toBeNull();
  });

  it("returns a Finding when target file is not loaded", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: { file: "Ghost.esp" }, ctx });
    expect(f).not.toBeNull();
    expect(f!.ruleId).toBe("LOAD001");
    expect(f!.matched.file).toBe("Ghost.esp");
  });

  it("returns null when no file arg is present (rule is targeted)", () => {
    const f = LOAD001.check({ tool: "xedit_read_record", args: {}, ctx });
    expect(f).toBeNull();
  });
});
