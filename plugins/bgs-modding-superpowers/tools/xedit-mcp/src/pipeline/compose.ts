import type { ZodTypeAny } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { Envelope, ToolContext } from "../types.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "./validate.js";
import { precheck, type PrecheckNeeds } from "./state-precheck.js";
import { runRules } from "./rules.js";
import { forwardCall } from "./forward.js";
import { emitAudit, hashArgs } from "../audit-line.js";

export interface ToolSpec {
  name: string;
  schema: ZodTypeAny;
  needs: PrecheckNeeds;
  /** Native daemon command this tool primarily wraps. */
  command: string;
  /** Build the human-readable summary string from the (validated) args. */
  summary: (args: Record<string, unknown>) => string;
  /** Optional post-processor for the daemon result before envelope. */
  shape?: (result: unknown) => unknown;
}

export interface RunToolInput {
  args: Record<string, unknown>;
  ctx: ToolContext;
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
}

export async function runTool(spec: ToolSpec, input: RunToolInput): Promise<Envelope> {
  try {
    const meta = { tool: spec.name };

    const v = validateArgs(spec.schema, input.args, meta);
    if (v) {
      await emitAudit({ audit: input.audit, tool: spec.name, args: input.args, env: v, ctx: input.ctx });
      return v;
    }

    const p = precheck({ tool: spec.name, args: input.args }, { ctx: input.ctx, needs: spec.needs });
    if (p) {
      await emitAudit({ audit: input.audit, tool: spec.name, args: input.args, env: p, ctx: input.ctx });
      return p;
    }

    const r = await runRules({ tool: spec.name, args: input.args, ctx: input.ctx, registry: input.registry });
    if (r.refusal) {
      await emitAudit({
        audit: input.audit,
        tool: spec.name,
        args: input.args,
        env: r.refusal,
        ctx: input.ctx,
        ruleHits: r.ruleHits,
      });
      return r.refusal;
    }

    const env = await forwardCall({
      tool: spec.name,
      command: spec.command,
      args: input.args,
      adapter: input.adapter,
      summary: spec.summary(input.args),
      shape: spec.shape,
    });

    if (env.ok && r.warnings.length) {
      env.warnings.push(...r.warnings);
    }

    await emitAudit({
      audit: input.audit,
      tool: spec.name,
      args: input.args,
      env,
      ctx: input.ctx,
      ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
    });
    return env;
  } catch (err) {
    // The harness spine must never let an unexpected throw escape unaudited and
    // un-enveloped. Map any infrastructure exception (adapter rejection, shaper
    // throw, summary throw, etc.) to an internal_error refusal.
    const refusal = refuse({
      tool: spec.name,
      summary: "Internal error during tool execution",
      code: MCP_ERROR_CODES.INTERNAL_ERROR,
      hint: err instanceof Error ? err.message : String(err),
    });
    await input.audit.append({
      tool: spec.name,
      argsHash: hashArgs(input.args),
      decision: "refused",
      ok: false,
      code: refusal.code,
      daemonPid: input.ctx.daemonPid,
      sessionId: input.ctx.sessionId,
    });
    return refusal;
  }
}
