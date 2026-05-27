import { describe, it, expect } from "vitest";
import { makeReadRecordHandler } from "../../src/tools/read-record.js";
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

describe("xedit_read_record tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-read-")) });

  it("returns composite read on the happy path", async () => {
    const adapter = makeMockAdapter({
      "records.get": () => ({
        formId: "0x012345",
        signature: "WEAP",
        editorId: "Foo",
        fields: { FULL: "Foo Name" },
      }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.base_record": () => ({ file: "Fallout4.esm", formId: "0x000045" }),
      "records.conflict_status": () => ({ status: "ITPO", details: "identical to previous override" }),
    });
    const handler = makeReadRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({
      record: { editorId: "Foo" },
      winningOverride: { file: "Patch.esp" },
      baseRecord: { file: "Fallout4.esm" },
      conflict: { status: "ITPO" },
    });
  });

  it("LOAD001 fires when file not loaded", async () => {
    const adapter = makeMockAdapter({});
    const handler = makeReadRecordHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });
});
