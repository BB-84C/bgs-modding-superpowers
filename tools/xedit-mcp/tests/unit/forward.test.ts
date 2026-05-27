import { describe, it, expect } from "vitest";
import { forwardCall } from "../../src/pipeline/forward.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";

describe("pipeline.forward", () => {
  it("returns ok envelope when daemon returns ok", async () => {
    const adapter = makeMockAdapter({
      "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
    });
    const env = await forwardCall({
      tool: "xedit_read_record",
      command: "records.get",
      args: { file: "X.esp", formId: "0x012345" },
      adapter,
      summary: "1 record",
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({ formId: "0x012345" });
  });

  it("maps daemon error to refusal with code=daemon_error", async () => {
    const adapter = makeMockAdapter({}); // unknown_command path
    const env = await forwardCall({
      tool: "xedit_call",
      command: "records.bogus",
      args: {},
      adapter,
      summary: "fail",
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("daemon_error");
    expect(env.detail).toMatchObject({ daemonCode: "unknown_command" });
  });

  it("maps mcp_mode_required distinctly", async () => {
    const wrapped = {
      async call(c: { command: string; args?: Record<string, unknown> }) {
        return {
          ok: false as const,
          command: c.command,
          error: { code: "mcp_mode_required", message: "need token" },
        };
      },
    };
    const env = await forwardCall({
      tool: "xedit_session",
      command: "system.describe",
      args: {},
      adapter: wrapped,
      summary: "describe",
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("mcp_mode_required");
    expect(env.hint).toContain("token");
  });
});
