import { describe, it, expect } from "vitest";
import { z } from "zod";
import { runTool, type ToolSpec } from "../../src/pipeline/compose.js";
import { defaultRegistry } from "../../src/rules/registry.js";
import { createAuditLogger } from "../../src/audit.js";
import { makeMockAdapter } from "../fixtures/daemon-mock.js";
import type { ToolContext } from "../../src/types.js";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const adapter = makeMockAdapter({
  "records.get": () => ({ formId: "0x012345", editorId: "Foo" }),
});

const ctx: ToolContext = {
  sessionId: "s",
  daemonPid: 1234,
  loadOrder: ["Patch.esp"],
  consentEnabled: false,
  capabilities: { contractVersion: "0.10", gameMode: "Fallout4", commands: [], fetchedAt: "" },
};

const spec: ToolSpec = {
  name: "xedit_read_record",
  schema: z.object({ file: z.string(), formId: z.string() }),
  needs: { daemon: true, targetFileFromArg: "file" },
  command: "records.get",
  summary: (args) => `record ${String(args.formId)}`,
};

describe("pipeline.compose.runTool", () => {
  const auditDir = mkdtempSync(join(tmpdir(), "xedit-mcp-compose-"));
  const audit = createAuditLogger({ baseDir: auditDir });
  const registry = defaultRegistry();

  it("returns ok envelope on the happy path and writes audit", async () => {
    const env = await runTool(spec, {
      args: { file: "Patch.esp", formId: "0x012345" },
      ctx, adapter, registry, audit,
    });
    expect(env.ok).toBe(true);
    if (!env.ok) throw new Error("expected ok");
    expect(env.data).toMatchObject({ formId: "0x012345" });
  });

  it("short-circuits on invalid args (stage 1)", async () => {
    const env = await runTool(spec, {
      args: { file: "Patch.esp" }, // missing formId
      ctx, adapter, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("invalid_request");
  });

  it("short-circuits on state precheck (stage 2)", async () => {
    const env = await runTool(spec, {
      args: { file: "Ghost.esp", formId: "0x012345" },
      ctx, adapter, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("state_violation");
  });

  it("short-circuits on rule (stage 3) — LOAD001 against xedit_find_record", async () => {
    const findSpec: ToolSpec = {
      name: "xedit_find_record",
      schema: z.object({ file: z.string() }),
      needs: {},
      command: "records.list",
      summary: () => "list",
    };
    const a2 = makeMockAdapter({ "records.list": () => ({ records: [] }) });
    const env = await runTool(findSpec, {
      args: { file: "Ghost.esp" },
      ctx, adapter: a2, registry, audit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("rule_LOAD001");
  });

  it("catches unexpected throws → internal_error envelope + writes audit line", async () => {
    const throwingAdapter = {
      async call(): Promise<never> { throw new Error("boom"); },
    };
    const errDir = mkdtempSync(join(tmpdir(), "xedit-mcp-compose-err-"));
    const errAudit = createAuditLogger({ baseDir: errDir });
    const env = await runTool(spec, {
      args: { file: "Patch.esp", formId: "0x012345" },
      ctx, adapter: throwingAdapter, registry, audit: errAudit,
    });
    if (env.ok) throw new Error("expected refusal");
    expect(env.code).toBe("internal_error");
    expect(env.hint).toBe("boom");

    const today = new Date().toISOString().slice(0, 10);
    const lines = readFileSync(join(errDir, `${today}.jsonl`), "utf8").trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(1);
    const last = JSON.parse(lines[lines.length - 1]);
    expect(last.code).toBe("internal_error");
    expect(last.tool).toBe("xedit_read_record");
  });
});
