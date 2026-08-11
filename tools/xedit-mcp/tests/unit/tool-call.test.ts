import { describe, it, expect } from "vitest";
import { makeCallHandler } from "../../src/tools/call.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s", daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_call atomic passthrough", () => {
  const audit = createAuditLogger({ baseDir: createTrackedTempDirSync("xedit-mcp-call-") });

  it("forwards a known command and returns the daemon result", async () => {
    const adapter = makeMockAdapter({
      "records.get": (a) => ({ formId: a.formId, fields: { FULL: "Hi" } }),
    });
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "records.get", args: { file: "Patch.esp", formId: "0x012345" } });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { fields: Record<string, string> }).fields.FULL).toBe("Hi");
  });

  it("refuses unknown command with hint pointing to capabilities digest", async () => {
    const adapter = makeMockAdapter({});
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "no.such.command", args: {} });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
    expect(env.hint).toContain("xedit_list_capabilities");
  });

  it("LOAD001 still fires against args.file even via passthrough", async () => {
    const adapter = makeMockAdapter({ "records.get": () => ({}) });
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => ctx });
    const env = await handler({ command: "records.get", args: { file: "Ghost.esp", formId: "0x012345" } });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("reports the exact successful session.save result to the pending-save owner", async () => {
    const result = {
      savedFilesNow: [],
      savedFilesPendingShutdown: [{ name: "Patch.esp", fileName: "Patch.esp" }],
      savedNowCount: 0,
      savePendingShutdownCount: 1,
      dirtyState: { dirty: false },
    };
    let observed: unknown;
    const adapter = makeMockAdapter({ "session.save": () => result });
    const handler = makeCallHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
      onSuccessfulSessionSave: (save) => { observed = save; },
    });

    const env = await handler({ command: "session.save", args: { files: ["Patch.esp"] } });

    expect(env.ok).toBe(true);
    expect(observed).toEqual(result);
  });

  it.each([
    { command: "session.flush", args: { force: false } },
    { command: "session.flush", args: "{\"force\":true}" },
  ])("refuses session.flush passthrough after args normalization: $args", async (input) => {
    let forwarded = false;
    const adapter = makeMockAdapter({
      "session.flush": () => { forwarded = true; return {}; },
    });
    const flushCtx: ToolContext = {
      ...ctx,
      capabilities: { ...ctx.capabilities!, commands: ["session.flush"] },
    };
    const handler = makeCallHandler({ adapter, registry: defaultRegistry(), audit, getContext: () => flushCtx });

    const env = await handler(input);

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
    expect(env.hint).toContain("xedit_flush");
    expect(forwarded).toBe(false);
  });
});
