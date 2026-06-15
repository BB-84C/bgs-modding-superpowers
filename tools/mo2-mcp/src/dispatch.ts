/** Central MCP tool-call dispatch: lookup -> schema validation -> rules -> handler. */
import { getTool } from "./tool-registry.js";
import { hashArgs } from "./audit.js";
import { runRules, hasBlocking } from "./pipeline/rules.js";
import type { Rule, ToolContext } from "./types.js";

export interface DispatchToolCallInput {
  toolName: string;
  rawArgs: unknown;
  ctx: ToolContext;
  rules: Rule[];
}

export interface DispatchToolCallResult {
  content: Array<{ type: "text"; text: string }>;
  isError?: boolean;
}

function jsonText(value: unknown): { type: "text"; text: string } {
  return { type: "text", text: JSON.stringify(value) };
}

export async function dispatchToolCall({
  toolName,
  rawArgs,
  ctx,
  rules,
}: DispatchToolCallInput): Promise<DispatchToolCallResult> {
  const t0 = Date.now();
  const tool = getTool(toolName);
  if (!tool) {
    await ctx.audit.log({
      ts: new Date().toISOString(),
      sessionId: ctx.sessionId,
      tool: toolName,
      argsHash: hashArgs(rawArgs),
      decision: "refused",
      durationMs: Date.now() - t0,
      error: { code: "tool_not_found", message: toolName },
    });
    return {
      content: [jsonText({ ok: false, error: { code: "tool_not_found" } })],
    };
  }

  const argsForParse = rawArgs ?? {};
  const parseResult = tool.inputSchema.safeParse(argsForParse);
  if (!parseResult.success) {
    const flat = parseResult.error.flatten();
    await ctx.audit.log({
      ts: new Date().toISOString(),
      sessionId: ctx.sessionId,
      tool: tool.name,
      argsHash: hashArgs(argsForParse),
      decision: "refused",
      durationMs: Date.now() - t0,
      error: {
        code: "invalid_arguments",
        message: "Tool arguments failed schema validation",
      },
      details: flat,
    });
    return {
      content: [
        jsonText({
          ok: false,
          error: {
            code: "invalid_arguments",
            message: "Tool arguments failed schema validation",
            field_errors: flat.fieldErrors,
            form_errors: flat.formErrors,
          },
        }),
      ],
      isError: true,
    };
  }

  const validatedArgs = parseResult.data as Record<string, unknown>;
  const findings = await runRules(rules, tool.name, ctx, validatedArgs);
  if (hasBlocking(findings)) {
    const blocking = findings.find((f) => f.decision === "block")!;
    await ctx.audit.log({
      ts: new Date().toISOString(),
      sessionId: ctx.sessionId,
      tool: tool.name,
      argsHash: hashArgs(argsForParse),
      decision: "refused",
      ruleFindings: findings,
      durationMs: Date.now() - t0,
      error: { code: blocking.code, message: blocking.message },
    });
    return {
      content: [jsonText({ ok: false, error: blocking })],
    };
  }

  try {
    const result = await tool.handler(validatedArgs, ctx);
    const mode = validatedArgs.mode as "plan" | "apply" | undefined;
    const resultObj = result as
      | { ok?: boolean; result?: { plan_id?: string; snapshot_id?: string } }
      | undefined;
    await ctx.audit.log({
      ts: new Date().toISOString(),
      sessionId: ctx.sessionId,
      tool: tool.name,
      mode,
      argsHash: hashArgs(argsForParse),
      decision:
        resultObj?.ok === false
          ? "refused"
          : mode === "plan"
            ? "plan_generated"
            : mode === "apply"
              ? "applied"
              : "ok",
      durationMs: Date.now() - t0,
      plan_id: resultObj?.result?.plan_id,
      snapshotId: resultObj?.result?.snapshot_id,
    });
    return { content: [jsonText(result)] };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    await ctx.audit.log({
      ts: new Date().toISOString(),
      sessionId: ctx.sessionId,
      tool: tool.name,
      argsHash: hashArgs(argsForParse),
      decision: "refused",
      durationMs: Date.now() - t0,
      error: { code: "internal_error", message: msg },
    });
    return {
      content: [
        jsonText({
          ok: false,
          error: { code: "internal_error", message: msg },
        }),
      ],
    };
  }
}
