import { describe, it, expect } from "vitest";
import { precheck } from "../../src/pipeline/state-precheck.js";
import type { ToolContext } from "../../src/types.js";

const baseCtx: ToolContext = {
  sessionId: "s1",
  daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  consentEnabled: false,
  mcpModeActive: false,
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("pipeline.precheck", () => {
  it("passes when no needs are declared", () => {
    const r = precheck({ tool: "t" }, { ctx: baseCtx, needs: {} });
    expect(r).toBeNull();
  });

  it("refuses if needsDaemon and pid is absent", () => {
    const r = precheck({ tool: "t" }, { ctx: { ...baseCtx, daemonPid: undefined }, needs: { daemon: true } });
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("state_violation");
    expect(r.hint).toContain("daemon");
  });

  it("refuses if needsConsent and consent flag is off", () => {
    const r = precheck({ tool: "t" }, { ctx: { ...baseCtx, consentEnabled: false }, needs: { consent: true } });
    if (!r || r.ok) throw new Error("expected refusal");
    expect(r.code).toBe("state_violation");
    expect(r.hint).toContain("IKnowWhatImDoing");
  });

  // Carry-forward #5 (Batch 2): `targetFileFromArg` was retired — load-order
  // checks now live in the rule layer (LOAD001). See state-precheck.ts
  // rationale comment for the reasoning.
});
