import { describe, it, expect } from "vitest";
import { makeInspectConflictsHandler } from "../../src/tools/inspect-conflicts.js";
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
  loadOrder: ["Fallout4.esm", "Patch.esp", "Other.esp"],
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

describe("xedit_inspect_conflicts tool", () => {
  const audit = createAuditLogger({ baseDir: mkdtempSync(join(tmpdir(), "xedit-mcp-conflict-")) });

  it("verdict=no_conflict when conflict_status reports no_conflict", async () => {
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({ status: "no_conflict" }),
      "records.winning_override": () => ({ file: "Patch.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [] }),
    });
    const handler = makeInspectConflictsHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { verdict: string }).verdict).toBe("no_conflict");
  });

  it("verdict=breaking when conflict_status reports a hard conflict label", async () => {
    const adapter = makeMockAdapter({
      "records.conflict_status": () => ({ status: "conflict_critical" }),
      "records.winning_override": () => ({ file: "Other.esp", formId: "0x012345" }),
      "records.referenced_by": () => ({ referencers: [{ file: "Mod.esp", formId: "0x55" }] }),
    });
    const handler = makeInspectConflictsHandler({
      adapter,
      registry: defaultRegistry(),
      audit,
      getContext: () => ctx,
    });
    const env = await handler({ file: "Patch.esp", formId: "0x012345" });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect((env.data as { verdict: string }).verdict).toBe("breaking");
  });
});
