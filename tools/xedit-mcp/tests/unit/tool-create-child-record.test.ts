import { describe, it, expect } from "vitest";
import { makeCreateChildRecordHandler } from "../../src/tools/create-child-record.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctxConsent: ToolContext = {
  sessionId: "sess-CCR",
  daemonPid: 4321,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  consentEnabled: true,
  capabilities: {
    contractVersion: "0.20",
    gameMode: "Fallout4",
    commands: [],
    fetchedAt: "",
    supports: { iKnowWhatImDoing: true, createParentSpec: true },
  },
};

const ctxNoConsent: ToolContext = {
  ...ctxConsent,
  consentEnabled: false,
  capabilities: { ...ctxConsent.capabilities!, supports: { iKnowWhatImDoing: false } },
};

describe("xedit_create_child_record tool", () => {
  it("forwards a CELL/QUST-style child record (subGroup path)", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-ccr-sub-"));
    const audit = createAuditLogger({ baseDir });
    let forwarded: Record<string, unknown> | undefined;
    const adapter = makeMockAdapter({
      "records.create": (args) => {
        forwarded = args;
        return { file: "Patch.esp", formId: "01000ABC", signature: "REFR" };
      },
    });
    const handler = makeCreateChildRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctxConsent,
    });
    const env = await handler({
      targetFile: "Patch.esp",
      signature: "REFR",
      parent: { parentFile: "Patch.esp", parentFormId: "0x01000123", subGroup: "Temporary" },
      editorId: "MyChildRef",
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(forwarded).toBeDefined();
    // parentFormId 0x prefix stripped before forwarding.
    expect((forwarded!.parent as Record<string, unknown>).parentFormId).toBe("01000123");
    expect((forwarded!.parent as Record<string, unknown>).subGroup).toBe("Temporary");
    expect(forwarded!.editorId).toBe("MyChildRef");
  });

  it("forwards a WRLD exterior child record (coords path)", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-ccr-coords-"));
    const audit = createAuditLogger({ baseDir });
    let forwarded: Record<string, unknown> | undefined;
    const adapter = makeMockAdapter({
      "records.create": (args) => {
        forwarded = args;
        return { file: "Patch.esp", formId: "01000DEF", signature: "REFR" };
      },
    });
    const handler = makeCreateChildRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctxConsent,
    });
    const env = await handler({
      targetFile: "Patch.esp",
      signature: "REFR",
      parent: { parentFile: "Fallout4.esm", parentFormId: "0x0000003C", coords: [-2, 7] },
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const parent = (forwarded!.parent as Record<string, unknown>);
    expect(parent.coords).toEqual([-2, 7]);
    expect(parent.subGroup).toBeUndefined();
  });

  it("fast-fails with mutation_requires_iknowwhatimdoing when consent is not active", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-ccr-noconsent-"));
    const audit = createAuditLogger({ baseDir });
    let daemonCalled = 0;
    const adapter = makeMockAdapter({
      "records.create": () => {
        daemonCalled += 1;
        return {};
      },
    });
    const handler = makeCreateChildRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctxNoConsent,
    });
    const env = await handler({
      targetFile: "Patch.esp",
      signature: "REFR",
      parent: { parentFile: "Patch.esp", parentFormId: "0x01000123", subGroup: "Temporary" },
    });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("mutation_requires_iknowwhatimdoing");
    expect(daemonCalled).toBe(0);
  });

  it("refuses when parent supplies both subGroup and coords", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-ccr-mutex-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeCreateChildRecordHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctxConsent,
    });
    const env = await handler({
      targetFile: "Patch.esp",
      signature: "REFR",
      parent: {
        parentFile: "Patch.esp",
        parentFormId: "0x01000123",
        subGroup: "Persistent",
        coords: [0, 0],
      },
    });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("refuses on bogus signature", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-ccr-sig-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeCreateChildRecordHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctxConsent,
    });
    const env = await handler({
      targetFile: "Patch.esp",
      signature: "ref", // wrong length / case
      parent: { parentFile: "Patch.esp", parentFormId: "0x01000123" },
    });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});
