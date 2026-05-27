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

const CallArgs = z.object({
  command: z.string().min(1),
  args: z.record(z.unknown()).optional(),
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
    const v = validateArgs(CallArgs, rawArgs, { tool: "xedit_call" });
    if (v) {
      await opts.audit.append({ tool: "xedit_call", argsHash: "v-fail", decision: "refused", ok: false, code: v.code });
      return v;
    }

    const { command, args = {} } = rawArgs as { command: string; args?: Record<string, unknown> };

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
      await opts.audit.append({ tool: "xedit_call", argsHash: "unknown", decision: "refused", ok: false, code: env.code });
      return env;
    }

    // precheck uses daemon only; load-order owned by LOAD001 rule.
    const p = precheck({ tool: "xedit_call", args }, { ctx, needs: { daemon: true } });
    if (p) {
      await opts.audit.append({ tool: "xedit_call", argsHash: "p-fail", decision: "refused", ok: false, code: p.code });
      return p;
    }

    // Rules opt-in by listing "xedit_call" in appliesTo. LOAD001 lists it already.
    const r = await runRules({ tool: "xedit_call", args, ctx, registry: opts.registry });
    if (r) {
      await opts.audit.append({
        tool: "xedit_call",
        argsHash: "r-fail",
        decision: "refused",
        ok: false,
        code: r.code,
        ruleHits: [r.code.replace(/^rule_/, "")],
      });
      return r;
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
    await opts.audit.append({
      tool: "xedit_call",
      argsHash: "ok",
      decision: env.ok ? "ok" : "refused",
      ok: env.ok,
      code: env.ok ? undefined : env.code,
    });
    return env;
  };
}
