import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { emitAudit } from "../audit-line.js";

const Args = z.object({
  file: z.string().min(1),
  // Accept both "0x0000003C" and bare "0000003C" — strip 0x before forwarding to daemon.
  formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});

/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args: Record<string, unknown>): Record<string, unknown> {
  if (typeof args.formId !== "string") return args;
  const f = args.formId;
  return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}

export interface ReadRecordOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeReadRecordHandler(opts: ReadRecordOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_read_record",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }

    const v = validateArgs(Args, args, { tool: "xedit_read_record" });
    if (v) {
      await emitAudit({ audit: opts.audit, tool: "xedit_read_record", args, env: v, ctx });
      return v;
    }

    // NOTE: precheck uses `daemon` only; load-order is owned by LOAD001 rule.
    const p = precheck({ tool: "xedit_read_record", args }, { ctx, needs: { daemon: true } });
    if (p) {
      await emitAudit({ audit: opts.audit, tool: "xedit_read_record", args, env: p, ctx });
      return p;
    }

    const r = await runRules({ tool: "xedit_read_record", args, ctx, registry: opts.registry });
    if (r.refusal) {
      await emitAudit({
        audit: opts.audit,
        tool: "xedit_read_record",
        args,
        env: r.refusal,
        ctx,
        ruleHits: r.ruleHits,
      });
      return r.refusal;
    }

    const daemonArgs = stripFormIdPrefix(args);
    const [rec, win, base, conflict] = await Promise.all([
      opts.adapter.call({ command: "records.get", args: daemonArgs }),
      opts.adapter.call({ command: "records.winning_override", args: daemonArgs }),
      opts.adapter.call({ command: "records.base_record", args: daemonArgs }),
      opts.adapter.call({ command: "records.conflict_status", args: daemonArgs }),
    ]);

    if (!rec.ok) {
      const env = refuse({
        tool: "xedit_read_record",
        summary: `records.get failed: ${rec.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: rec.error.message,
        detail: { daemonCode: rec.error.code },
      });
      await emitAudit({ audit: opts.audit, tool: "xedit_read_record", args, env, ctx });
      return env;
    }

    const env = okEnv({
      tool: "xedit_read_record",
      summary: `read ${String(args.formId)} in ${String(args.file)}`,
      status: "completed",
      data: {
        record: rec.result,
        winningOverride: win.ok ? win.result : null,
        baseRecord: base.ok ? base.result : null,
        conflict: conflict.ok ? conflict.result : null,
      },
      warnings: r.warnings,
    });
    await emitAudit({
      audit: opts.audit,
      tool: "xedit_read_record",
      args,
      env,
      ctx,
      ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
    });
    return env;
  };
}
