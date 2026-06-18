import { describe, it, expect } from "vitest";
import { makeInspectConflictsDeepHandler } from "../../src/tools/inspect-conflicts-deep.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ctx: ToolContext = {
  sessionId: "sess-ICD",
  daemonPid: 4321,
  loadOrder: ["Fallout4.esm", "Patch.esp", "Other.esp"],
  capabilities: { contractVersion: "0.20", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_inspect_conflicts_deep tool", () => {
  it("surfaces the r6 childGroup sub-block in data.childGroup", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-deep-"));
    const audit = createAuditLogger({ baseDir });
    const childGroup = {
      all: "conflict_partitioned",
      conflicts: [{ path: "REFR/0x01000123", status: "itm" }],
    };
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({
        conflict: { all: "no_conflict", participants: [] },
        childGroup,
      }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [] }),
    });
    const handler = makeInspectConflictsDeepHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    const data = env.data as { verdict: string; childGroup: unknown; references?: unknown };
    expect(data.verdict).toBe("no_conflict");
    expect(data.childGroup).toEqual(childGroup);
    expect(data.references, "must NOT include references when includeReferences omitted").toBeUndefined();
  });

  it("chains records.references {recursive:true} when includeReferences=true", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-deep-refs-"));
    const audit = createAuditLogger({ baseDir });
    let referencesCalled = 0;
    let referencesRecursive: unknown = undefined;
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({
        conflict: { all: "no_conflict", participants: [] },
        childGroup: null,
      }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [] }),
      "records.references": (args) => {
        referencesCalled += 1;
        referencesRecursive = (args as { recursive?: unknown }).recursive;
        return { refs: [{ file: "Other.esp", formId: "0x55" }], depth: 3 };
      },
    });
    const handler = makeInspectConflictsDeepHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345", includeReferences: true });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(referencesCalled).toBe(1);
    expect(referencesRecursive).toBe(true);
    const data = env.data as { references: { refs: unknown[] } };
    expect(data.references.refs).toHaveLength(1);
  });

  it("LOAD001 fires when file not in load order", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-deep-load-"));
    const audit = createAuditLogger({ baseDir });
    const adapter = makeMockAdapter({});
    const handler = makeInspectConflictsDeepHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Ghost.esp", formId: "0x012345" });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("refuses on invalid formId", async () => {
    const baseDir = mkdtempSync(join(tmpdir(), "xedit-mcp-deep-bad-"));
    const audit = createAuditLogger({ baseDir });
    const handler = makeInspectConflictsDeepHandler({
      adapter: makeMockAdapter({}),
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "not-hex" });
    expect(env.ok).toBe(false);
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });
});
