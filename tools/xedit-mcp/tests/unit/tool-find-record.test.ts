import { describe, it, expect } from "vitest";
import { makeFindRecordHandler } from "../../src/tools/find-record.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_find_record tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-find-")) });

  it("by formId returns a slim locator", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_form_id": (args) => ({
        file: args.file,
        formId: args.formId,
        signature: "WEAP",
        editorId: "Foo",
      }),
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      locators: [{ file: "Patch.esp", formId: "0x012345", signature: "WEAP", editorId: "Foo" }],
    });
  });

  it("LOAD001 fires when file not in load order", async () => {
    const adapter = makeMockAdapter({ "records.find_by_form_id": () => ({}) });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("by editorId across all loaded files", async () => {
    const adapter = makeMockAdapter({
      "records.find_by_editor_id": () => ({
        matches: [{ file: "Patch.esp", formId: "0x0123", signature: "WEAP", editorId: "Foo" }],
      }),
    });
    const handler = makeFindRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ editorId: "Foo" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { locators: unknown[] }).locators).toHaveLength(1);
  });
});
