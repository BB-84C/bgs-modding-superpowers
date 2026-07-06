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
    // Daemon contract 0.20 requires `files: string[]`; intent tool's singular
    // `file` MUST be wrapped before forwarding. Verified empirically against
    // FO4 r6 daemon 2026-06-18 — omitting `files` triggers invalid_request.
    expect(forwarded!.files).toEqual(["Patch.esp"]);
    expect(forwarded!.file).toBeUndefined();
    const data = env.data as { matches: unknown[]; matchCount: number; truncated: boolean };
    expect(data.matches).toHaveLength(2);
    expect(data.matchCount).toBe(2);
    expect(data.truncated).toBe(false);
  });

  it("forwards offset verbatim to records.apply_filter", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-offset-"));
    const audit = createAuditLogger({ baseDir });
    let forwarded: Record<string, unknown> | undefined;
    const adapter = makeMockAdapter({
      "records.apply_filter": (args) => {
        forwarded = args;
        return { matches: [], matchCount: 0, offset: 25, limit: 50, truncated: false };
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });

    const env = await handler({ file: "Patch.esp", signatures: ["REFR"], limit: 50, offset: 25 });

    expect(env.ok).toBe(true);
    expect(forwarded).toBeDefined();
    expect(forwarded!.offset).toBe(25);
  });

  it("surfaces r7 pagination fields from daemon result", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-page-fields-"));
    const audit = createAuditLogger({ baseDir });
    const adapter = makeMockAdapter({
      "records.apply_filter": () => ({
        matches: [{ file: "Patch.esp", formId: "01000001", signature: "REFR" }],
        matchCount: 1,
        truncated: true,
        offset: 100,
        limit: 100,
        nextOffset: 200,
      }),
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });

    const env = await handler({ file: "Patch.esp", signatures: ["REFR"], offset: 100 });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as { offset?: number; limit?: number; nextOffset?: number; truncated: boolean };
    expect(data.offset).toBe(100);
    expect(data.limit).toBe(100);
    expect(data.nextOffset).toBe(200);
    expect(data.truncated).toBe(true);
  });

  it("rejects limit above contract 0.21 max before daemon call", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-limit-"));
    const audit = createAuditLogger({ baseDir });
    let called = false;
    const adapter = makeMockAdapter({
      "records.apply_filter": () => {
        called = true;
        return { matches: [] };
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });

    const env = await handler({ file: "Patch.esp", signatures: ["REFR"], limit: 101 });

    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_arguments");
    expect(called).toBe(false);
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

  it("drainAll follows nextOffset pages and aggregates matches without forwarding drainAll", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-drain-"));
    const audit = createAuditLogger({ baseDir });
    const forwarded: Array<Record<string, unknown>> = [];
    const pages = [
      {
        matches: [{ locator: { file: "Patch.esp", formId: "01000001" }, object: { signature: "REFR" } }],
        matchCount: 1,
        truncated: true,
        offset: 0,
        limit: 2,
        nextOffset: 2,
      },
      {
        matches: [{ locator: { file: "Patch.esp", formId: "01000002" }, object: { signature: "REFR" } }],
        matchCount: 1,
        truncated: true,
        offset: 2,
        limit: 2,
        nextOffset: 4,
        regexSlotsExhausted: true,
      },
      {
        matches: [{ locator: { file: "Patch.esp", formId: "01000003" }, object: { signature: "REFR" } }],
        matchCount: 1,
        truncated: false,
        offset: 4,
        limit: 2,
      },
    ];
    const adapter = makeMockAdapter({
      "records.apply_filter": (args) => {
        forwarded.push(args);
        return pages[forwarded.length - 1];
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });

    const env = await handler({ file: "Patch.esp", signatures: ["REFR"], limit: 2, drainAll: true });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(forwarded).toHaveLength(3);
    expect(forwarded.map((args) => args.offset)).toEqual([undefined, 2, 4]);
    expect(forwarded.every((args) => args.drainAll === undefined)).toBe(true);
    const data = env.data as {
      matches: Array<Record<string, unknown>>;
      truncated: boolean;
      nextOffset?: number;
      pagesFetched?: number;
      regexSlotsExhausted?: boolean;
    };
    expect(data.matches.map((m) => m.formId)).toEqual(["01000001", "01000002", "01000003"]);
    expect(data.pagesFetched).toBe(3);
    expect(data.truncated).toBe(false);
    expect(data.nextOffset).toBeUndefined();
    expect(data.regexSlotsExhausted).toBe(true);
  });

  it("drainAll stops at the 20 page safety cap and returns continuation metadata", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-fbp-drain-cap-"));
    const audit = createAuditLogger({ baseDir });
    const forwarded: Array<Record<string, unknown>> = [];
    const adapter = makeMockAdapter({
      "records.apply_filter": (args) => {
        forwarded.push(args);
        const offset = typeof args.offset === "number" ? args.offset : 0;
        return {
          matches: [{ file: "Patch.esp", formId: offset.toString(16).padStart(8, "0"), signature: "REFR" }],
          matchCount: 1,
          truncated: true,
          offset,
          limit: 1,
          nextOffset: offset + 1,
        };
      },
    });
    const handler = makeFindRecordsByPatternHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });

    const env = await handler({ file: "Patch.esp", signatures: ["REFR"], limit: 1, drainAll: true });

    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(forwarded).toHaveLength(20);
    const data = env.data as {
      matches: unknown[];
      truncated: boolean;
      drainCapped?: boolean;
      nextOffset?: number;
      pagesFetched?: number;
      drainCapNote?: string;
    };
    expect(data.matches).toHaveLength(20);
    expect(data.pagesFetched).toBe(20);
    expect(data.drainCapped).toBe(true);
    expect(data.truncated).toBe(true);
    expect(data.nextOffset).toBe(20);
    expect(data.drainCapNote).toContain("20 pages");
  });
});
