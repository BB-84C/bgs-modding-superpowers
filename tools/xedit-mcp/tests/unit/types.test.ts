import { describe, it, expect } from "vitest";
import type { Envelope, Rule, Finding, ToolContext } from "../../src/types.js";
import { MCP_ERROR_CODES } from "../../src/types.js";

describe("types", () => {
  it("MCP_ERROR_CODES contains required Batch 1 codes", () => {
    expect(MCP_ERROR_CODES.INVALID_REQUEST).toBe("invalid_request");
    expect(MCP_ERROR_CODES.STATE_VIOLATION).toBe("state_violation");
    expect(MCP_ERROR_CODES.DAEMON_ERROR).toBe("daemon_error");
    expect(MCP_ERROR_CODES.MCP_MODE_REQUIRED).toBe("mcp_mode_required");
  });

  it("Envelope discriminates ok=false vs ok=true at compile time", () => {
    const ok: Envelope = { ok: true, tool: "x", summary: "s", warnings: [] };
    const bad: Envelope = {
      ok: false, tool: "x", summary: "s", warnings: [],
      code: "invalid_request", hint: "h",
    };
    expect(ok.ok).toBe(true);
    expect(bad.ok).toBe(false);
  });

  it("Envelope narrows so refusal-only fields are inaccessible on ok branch", () => {
    const refusal: Envelope = {
      ok: false, tool: "x", summary: "s", warnings: [],
      code: "invalid_request", hint: "h",
    };
    if (!refusal.ok) {
      // code is reachable on the refusal branch
      expect(refusal.code).toBe("invalid_request");
    }

    const success: Envelope = { ok: true, tool: "x", summary: "s", warnings: [] };
    if (success.ok) {
      // @ts-expect-error code does not exist on EnvelopeOk
      success.code;
      // @ts-expect-error hint does not exist on EnvelopeOk
      success.hint;
    }
    expect(success.ok).toBe(true);
  });
});
