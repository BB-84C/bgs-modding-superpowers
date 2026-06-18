import { describe, it, expect } from "vitest";
import { makeNavigateAncestryHandler } from "../../src/tools/navigate-ancestry.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "sess-NA",
  daemonPid: 4321,
  loadOrder: ["Fallout4.esm", "Patch.esp"],
  capabilities: { contractVersion: "0.20", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_navigate_ancestry tool", () => {
  it("formId mode: forces includeParents:true and flattens relations.parents", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-na-fid-"));
    const audit = createAuditLogger({ baseDir });
    let getArgs: Record<string, unknown> | undefined;
    let edidCalls = 0;
    const adapter = makeMockAdapter({
      "records.get": (args) => {
        getArgs = args;
        return {
          file: args.file,
          formId: args.formId,
          signature: "REFR",
          relations: {
            parents: [
              { locator: { file: "Patch.esp", formId: "01000001" }, object: { signature: "CELL", editorId: "TestCell" } },
              { locator: { file: "Fallout4.esm", formId: "0000003C" }, object: { signature: "WRLD", editorId: "Commonwealth" } },
            ],
          },
        };
      },
      "records.find_by_editor_id": () => {
        edidCalls += 1;
        return { hits: [] };
      },
    });
    const handler = makeNavigateAncestryHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x01000ABC" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(getArgs).toBeDefined();
    expect(getArgs!.includeParents).toBe(true);
    expect(getArgs!.formId).toBe("01000ABC"); // 0x stripped
    expect(edidCalls).toBe(0);
    const data = env.data as { ancestors: Array<Record<string, unknown>>; depth: number };
    expect(data.ancestors).toHaveLength(2);
    expect(data.depth).toBe(2);
    expect(data.ancestors[0].editorId).toBe("TestCell");
    expect(data.ancestors[1].editorId).toBe("Commonwealth");
  });

  it("editorId mode: routes to records.find_by_editor_id with includeParents:true", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-na-edid-"));
    const audit = createAuditLogger({ baseDir });
    let edidArgs: Record<string, unknown> | undefined;
    let getCalls = 0;
    const adapter = makeMockAdapter({
      "records.get": () => {
        getCalls += 1;
        return {};
      },
      "records.find_by_editor_id": (args) => {
        edidArgs = args;
        return {
          hits: [
            {
              locator: { file: "Patch.esp", formId: "01000ABC", path: "" },
              object: {
                signature: "REFR",
                editorId: "MyChildRef",
                relations: {
                  parents: [
                    { locator: { file: "Patch.esp", formId: "01000001" }, object: { signature: "CELL" } },
                  ],
                },
              },
            },
          ],
        };
      },
    });
    const handler = makeNavigateAncestryHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ editorId: "MyChildRef" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(edidArgs).toBeDefined();
    expect(edidArgs!.includeParents).toBe(true);
    expect(edidArgs!.editorId).toBe("MyChildRef");
    expect(getCalls).toBe(0);
    const data = env.data as { ancestors: unknown[]; depth: number };
    expect(data.ancestors).toHaveLength(1);
    expect(data.depth).toBe(1);
  });

  it("refuses when neither mode validates", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-na-bad-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeNavigateAncestryHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({});
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("handles placeholder file + zero formId + valid editorId by routing to editorId mode", async () => {
    // Mirrors find-record's placeholder-aware behaviour so weak callers still
    // land in the right mode instead of hitting LOAD001 on a placeholder file.
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-na-placeholder-"));
    const audit = createAuditLogger({ baseDir });
    let edidCalled = 0;
    const adapter = makeMockAdapter({
      "records.find_by_editor_id": () => {
        edidCalled += 1;
        return {
          hits: [
            {
              locator: { file: "Patch.esp", formId: "01000ABC" },
              object: { signature: "REFR", relations: { parents: [] } },
            },
          ],
        };
      },
    });
    const handler = makeNavigateAncestryHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "", formId: "0x00000000", editorId: "MyChildRef" });
    expect(env.ok).toBe(true);
    expect(edidCalled).toBe(1);
  });

  it("LOAD001 fires when file not in load order", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-na-load-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeNavigateAncestryHandler({
      adapter: makeMockAdapter({ "records.get": () => ({}) }),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Ghost.esp", formId: "0x01000ABC" });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });
});
