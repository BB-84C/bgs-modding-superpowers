import { describe, expect, it, beforeEach } from "vitest";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { z } from "zod";
import { dispatchToolCall } from "../src/dispatch.js";
import { AuditLogger, hashArgs } from "../src/audit.js";
import { PlanCache } from "../src/plan-apply.js";
import { SnapshotManager } from "../src/snapshot.js";
import { _clearToolsForTests, registerTool } from "../src/tool-registry.js";
import type { Rule, ToolContext } from "../src/types.js";

const toggleSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), name: z.string(), enabled: z.boolean() }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

async function makeCtx(sessionId = "test-session"): Promise<ToolContext> {
  const root = await mkdtemp(join(tmpdir(), "mo2-mcp-dispatch-"));
  return {
    config: {
      mo2Root: root,
      permissionCeiling: "metadata-editable" as const,
      allowedProfiles: ["Default"],
      deny: [],
      snapshotRoot: join(root, "snapshots"),
      auditRoot: join(root, "audit"),
    },
    sessionId,
    plans: new PlanCache(),
    snapshots: new SnapshotManager(join(root, "snapshots"), sessionId),
    audit: new AuditLogger(join(root, "audit"), sessionId),
  } satisfies ToolContext;
}

function responseJson(result: { content: Array<{ type: "text"; text: string }> }): unknown {
  return JSON.parse(result.content[0].text) as unknown;
}

async function readOnlyAuditRecord(ctx: ToolContext): Promise<Record<string, unknown>> {
  const files = await readdir(ctx.config.auditRoot);
  const content = await readFile(join(ctx.config.auditRoot, files[0]), "utf8");
  return JSON.parse(content.trim().split("\n")[0]) as Record<string, unknown>;
}

describe("central dispatch Zod inputSchema enforcement", () => {
  beforeEach(() => {
    _clearToolsForTests();
  });

  it("returns invalid_arguments for missing required plan args", async () => {
    registerTool({
      name: "mo2_toggle_mod",
      tier: "T3",
      description: "test toggle",
      inputSchema: toggleSchema,
      handler: async () => ({ ok: true }),
    });
    const ctx = await makeCtx();

    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "plan" },
      ctx,
      rules: [],
    });

    expect(result.isError).toBe(true);
    expect(responseJson(result)).toMatchObject({
      ok: false,
      error: { code: "invalid_arguments" },
    });
  });

  it("returns invalid_arguments for wrong arg types", async () => {
    registerTool({
      name: "mo2_toggle_mod",
      tier: "T3",
      description: "test toggle",
      inputSchema: toggleSchema,
      handler: async () => ({ ok: true }),
    });
    const ctx = await makeCtx();

    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "plan", name: 42, enabled: true },
      ctx,
      rules: [],
    });

    expect(responseJson(result)).toMatchObject({
      ok: false,
      error: { code: "invalid_arguments" },
    });
  });

  it("returns invalid_arguments for invalid mode discriminators", async () => {
    registerTool({
      name: "mo2_toggle_mod",
      tier: "T3",
      description: "test toggle",
      inputSchema: toggleSchema,
      handler: async () => ({ ok: true }),
    });
    const ctx = await makeCtx();

    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "elite_hack" },
      ctx,
      rules: [],
    });

    expect(responseJson(result)).toMatchObject({
      ok: false,
      error: { code: "invalid_arguments" },
    });
  });

  it("runs the handler for valid parsed args", async () => {
    let handlerRan = false;
    registerTool({
      name: "mock_read_tool",
      tier: "T1",
      description: "mock read",
      inputSchema: z.object({ mode: z.literal("read"), name: z.string() }),
      handler: async () => {
        handlerRan = true;
        return { ok: true, result: "ran" };
      },
    });
    const ctx = await makeCtx();

    const result = await dispatchToolCall({
      toolName: "mock_read_tool",
      rawArgs: { mode: "read", name: "MyMod" },
      ctx,
      rules: [],
    });

    expect(handlerRan).toBe(true);
    expect(responseJson(result)).toEqual({ ok: true, result: "ran" });
  });

  it("logs invalid_arguments refusals with field errors and the raw args hash", async () => {
    registerTool({
      name: "mo2_toggle_mod",
      tier: "T3",
      description: "test toggle",
      inputSchema: toggleSchema,
      handler: async () => ({ ok: true }),
    });
    const ctx = await makeCtx("audit-session");
    const rawArgs = { mode: "plan" };

    await dispatchToolCall({ toolName: "mo2_toggle_mod", rawArgs, ctx, rules: [] });

    const record = await readOnlyAuditRecord(ctx);
    expect(record.tool).toBe("mo2_toggle_mod");
    expect(record.decision).toBe("refused");
    expect(record.argsHash).toBe(hashArgs(rawArgs));
    expect(record.error).toEqual({
      code: "invalid_arguments",
      message: "Tool arguments failed schema validation",
    });
    expect(record.details).toMatchObject({ fieldErrors: { name: expect.any(Array) } });
  });

  it("validates before rules", async () => {
    registerTool({
      name: "mo2_toggle_mod",
      tier: "T3",
      description: "test toggle",
      inputSchema: toggleSchema,
      handler: async () => ({ ok: true }),
    });
    const blockingRule: Rule = {
      id: "BLOCK001",
      severity: "CRITICAL",
      appliesTo: () => true,
      evaluate: async () => ({
        code: "BLOCK001",
        severity: "CRITICAL",
        decision: "block",
        message: "rule should not run before schema validation",
      }),
    };
    const ctx = await makeCtx();

    const result = await dispatchToolCall({
      toolName: "mo2_toggle_mod",
      rawArgs: { mode: "plan" },
      ctx,
      rules: [blockingRule],
    });

    expect(responseJson(result)).toMatchObject({
      ok: false,
      error: { code: "invalid_arguments" },
    });
  });

  it("passes parsed args, not the raw object, to handlers", async () => {
    let capturedArgs: Record<string, unknown> | undefined;
    registerTool({
      name: "mock_defaulting_tool",
      tier: "T1",
      description: "mock defaulting",
      inputSchema: z.object({
        mode: z.literal("plan"),
        name: z.string(),
        profile: z.string().default("Default"),
      }),
      handler: async (args) => {
        capturedArgs = args;
        return { ok: true };
      },
    });
    const ctx = await makeCtx();

    await dispatchToolCall({
      toolName: "mock_defaulting_tool",
      rawArgs: { mode: "plan", name: "MyMod", raw_extra: "stripped" },
      ctx,
      rules: [],
    });

    expect(capturedArgs).toEqual({ mode: "plan", name: "MyMod", profile: "Default" });
  });
});
