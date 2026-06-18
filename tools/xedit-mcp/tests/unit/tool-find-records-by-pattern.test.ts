import { describe, it, expect } from "vitest";
import { makeFindRecordsByPatternHandler } from "../../src/tools/find-records-by-pattern.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "sess-FBP",
  daemonPid: 4321,
  loadOrder: ["Fallout4.esm", "Patch.esp", "Other.esp"],
  capabilities: { contractVersion: "0.20", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_find_records_by_pattern tool", () => {
  it("forwards regex args to records.apply_filter and projects matches", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-"));
    const audit = createAuditLogger({ baseDir });
    let forwarded: Record<string, unknown> | undefined;
    const adapter = makeMockAdapter({
      "records.apply_filter": (args) => {
        forwarded = args;
        return {
          matches: [
            { file: "Patch.esp", formId: "01000001", signature: "REFR", editorId: "IronTest" },
            { file: "Patch.esp", formId: "01000002", signature: "REFR", editorId: "SteelTest" },
          ],
          matchCount: 2,
          truncated: false,
        };
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({
      file: "Patch.esp",
      signatures: ["REFR"],
      editorIdRegex: "^(Iron|Steel)",
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(forwarded).toBeDefined();
    expect(forwarded!.signatures).toEqual(["REFR"]);
    expect(forwarded!.editorIdRegex).toBe("^(Iron|Steel)");
    const data = env.data as { matches: unknown[]; matchCount: number; truncated: boolean };
    expect(data.matches).toHaveLength(2);
    expect(data.matchCount).toBe(2);
    expect(data.truncated).toBe(false);
  });

  it("accepts an array for multi-pattern OR", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-multi-"));
    const audit = createAuditLogger({ baseDir });
    let forwarded: Record<string, unknown> | undefined;
    const adapter = makeMockAdapter({
      "records.apply_filter": (args) => {
        forwarded = args;
        return { matches: [], matchCount: 0 };
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({
      parentFormId: "0x01000123",
      editorIdRegex: ["^Iron", "^Steel"],
    });
    expect(env.ok).toBe(true);
    expect(forwarded).toBeDefined();
    expect(forwarded!.editorIdRegex).toEqual(["^Iron", "^Steel"]);
    // parentFormId hex prefix stripped before forwarding.
    expect(forwarded!.parentFormId).toBe("01000123");
  });

  it("refuses when no filter predicate is supplied", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-empty-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeFindRecordsByPatternHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    // file + limit alone are NOT predicates — must refuse.
    const env = await handler({ file: "Patch.esp", limit: 100 });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("refuses when editorIdPattern and editorIdRegex are both supplied", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-mutex-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeFindRecordsByPatternHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({
      editorIdPattern: "Iron*",
      editorIdRegex: "^Iron",
    });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("unwraps daemon { locator, object } match shape", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-unwrap-"));
    const audit = createAuditLogger({ baseDir });
    const adapter = makeMockAdapter({
      "records.apply_filter": () => ({
        matches: [
          {
            locator: { file: "Other.esp", formId: "02000001", path: "REFR\\02000001" },
            object: { signature: "REFR", editorId: "IronOverride", displayName: "Iron Bar" },
          },
        ],
        matchCount: 1,
      }),
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ signatures: ["REFR"], editorIdRegex: "Iron" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as { matches: Array<Record<string, unknown>> };
    expect(data.matches[0].file).toBe("Other.esp");
    expect(data.matches[0].editorId).toBe("IronOverride");
    expect(data.matches[0].signature).toBe("REFR");
  });
});
