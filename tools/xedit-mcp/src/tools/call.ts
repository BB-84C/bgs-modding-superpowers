import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { forwardCall } from "../pipeline/forward.js";
import { allDigestCommands } from "../capabilities-digest.js";
import { emitAudit } from "../audit-line.js";

// Some MCP clients serialize the `args` sub-object to a JSON string before
// sending. Accept either an object (canonical) or a string (which we parse).
const ArgsObject = z.record(z.unknown());
const ArgsStringParsed = z
  .string()
  .transform((s, ctx) => {
    const trimmed = s.trim();
    if (trimmed === "") return {} as Record<string, unknown>;
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "args string must parse to a JSON object (not array/null/primitive)",
        });
        return z.NEVER;
      }
      return parsed as Record<string, unknown>;
    } catch (err) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `args string must be valid JSON: ${(err as Error).message}`,
      });
      return z.NEVER;
    }
  });

const CallArgs = z.object({
  command: z.string().min(1),
  args: z.union([ArgsObject, ArgsStringParsed]).optional(),
});

export interface CallOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeCallHandler(opts: CallOptions) {
  const knownCommands = new Set(allDigestCommands());
  return async (rawArgs: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_call",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    // Validate AND normalize: if args came in as a string, Zod's transform parses it.
    const parsed = CallArgs.safeParse(rawArgs);
    if (!parsed.success) {
      const v = validateArgs(CallArgs, rawArgs, { tool: "xedit_call" });
      await emitAudit({ audit: opts.audit, tool: "xedit_call", args: rawArgs, env: v!, ctx });
      return v!;
    }
    const { command, args = {} } = parsed.data;

    // Allow live-daemon commands that exist in capabilities but not in the curated digest,
    // and warn. Reject only if both digest AND live capabilities lack the command.
    const liveCommands = new Set(ctx.capabilities?.commands ?? []);
    const knownToDigest = knownCommands.has(command);
    const knownToLive = liveCommands.has(command);
    if (!knownToDigest && !knownToLive) {
      const env = refuse({
        tool: "xedit_call",
        summary: `Unknown command: ${command}`,
        code: MCP_ERROR_CODES.INVALID_REQUEST,
        hint: "Check xedit_list_capabilities for the supported command set.",
        detail: { command },
      });
      await emitAudit({ audit: opts.audit, tool: "xedit_call", args: rawArgs, env, ctx });
      return env;
    }

    // precheck uses daemon only; load-order owned by LOAD001 rule.
    const p = precheck({ tool: "xedit_call", args }, { ctx, needs: { daemon: true } });
    if (p) {
      await emitAudit({ audit: opts.audit, tool: "xedit_call", args: rawArgs, env: p, ctx });
      return p;
    }

    // Rules opt-in by listing "xedit_call" in appliesTo. LOAD001 lists it already.
    const r = await runRules({ tool: "xedit_call", args, ctx, registry: opts.registry });
    if (r.refusal) {
      await emitAudit({
        audit: opts.audit,
        tool: "xedit_call",
        args: rawArgs,
        env: r.refusal,
        ctx,
        ruleHits: r.ruleHits,
      });
      return r.refusal;
    }

    const env = await forwardCall({
      tool: "xedit_call",
      command,
      args,
      adapter: opts.adapter,
      summary: `passthrough ${command}`,
    });
    if (env.ok && !knownToDigest) {
      env.warnings.push({
        code: "DIGEST_DRIFT",
        message: `Command ${command} present in live daemon but missing from curated digest. Consider updating capabilities-digest.ts.`,
        severity: "MEDIUM",
      });
    }
    if (env.ok && r.warnings.length) {
      env.warnings.push(...r.warnings);
    }
    await emitAudit({
      audit: opts.audit,
      tool: "xedit_call",
      args: rawArgs,
      env,
      ctx,
      ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
    });
    return env;
  };
}
