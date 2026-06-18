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
import { mapVerdict, type Verdict } from "../verdict.js";

// r6 supports.conflictStatusChildGroup (response-only `result.childGroup` sub-block,
// contract 0.15) + supports.referencesRecursive (records.references {recursive:true},
// contract 0.15). This tool surfaces both behind one call so the agent does not
// have to chain three daemon commands by hand.

const Args = z.object({
  file: z.string().min(1),
  // Accept both "0x0000003C" and bare "0000003C" — strip 0x before forwarding to daemon.
  formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
  // When true: chain records.references {recursive: true} so the agent can
  // see the outgoing reference tree on the winning override in one tool call.
  includeReferences: z.boolean().optional(),
});

/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args: Record<string, unknown>): Record<string, unknown> {
  if (typeof args.formId !== "string") return args;
  const f = args.formId;
  return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}

export interface InspectConflictsDeepOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeInspectConflictsDeepHandler(opts: InspectConflictsDeepOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_inspect_conflicts_deep",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }
    const v = validateArgs(Args, args, { tool: "xedit_inspect_conflicts_deep" });
    if (v) {
      await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts_deep", args, env: v, ctx });
      return v;
    }
    const p = precheck(
      { tool: "xedit_inspect_conflicts_deep", args },
      { ctx, needs: { daemon: true } },
    );
    if (p) {
      await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts_deep", args, env: p, ctx });
      return p;
    }
    const r = await runRules({
      tool: "xedit_inspect_conflicts_deep",
      args,
      ctx,
      registry: opts.registry,
    });
    if (r.refusal) {
      await emitAudit({
        audit: opts.audit,
        tool: "xedit_inspect_conflicts_deep",
        args,
        env: r.refusal,
        ctx,
        ruleHits: r.ruleHits,
      });
      return r.refusal;
    }

    const includeReferences = args.includeReferences === true;
    const daemonArgs = stripFormIdPrefix(args);
    // Strip the wrapper-only `includeReferences` flag before forwarding to the
    // daemon; the native commands have no such arg.
    const { includeReferences: _drop, ...coreArgs } = daemonArgs as Record<string, unknown>;

    const calls: Array<Promise<Awaited<ReturnType<DaemonAdapter["call"]>>>> = [
      opts.adapter.call({ command: "records.conflict_status", args: coreArgs }),
      opts.adapter.call({ command: "records.winning_override", args: coreArgs }),
      opts.adapter.call({ command: "records.referenced_by", args: coreArgs }),
    ];
    if (includeReferences) {
      calls.push(
        opts.adapter.call({
          command: "records.references",
          args: { ...coreArgs, recursive: true },
        }),
      );
    }
    const results = await Promise.all(calls);
    const [conflict, winning, referencedBy, referencesEnv] = results;

    if (!conflict.ok) {
      const env = refuse({
        tool: "xedit_inspect_conflicts_deep",
        summary: `records.conflict_status failed: ${conflict.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: conflict.error.message,
      });
      await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts_deep", args, env, ctx });
      return env;
    }

    // Real daemon shape (r6, contract 0.20):
    //   result: {
    //     conflict: { all, this, participants },
    //     childGroup?: { all, conflicts: [...] }   // supports.conflictStatusChildGroup
    //   }
    // Pre-0.15 / unit-test mock shape: flat `status` field.
    const conflictResult = conflict.result as {
      conflict?: { all?: string; this?: string; participants?: unknown[] };
      childGroup?: unknown;
      status?: string;
    };
    const rawStatus = String(conflictResult.conflict?.all ?? conflictResult.status ?? "unknown");
    const verdict: Verdict = mapVerdict(rawStatus);
    const participants = Array.isArray(conflictResult.conflict?.participants)
      ? conflictResult.conflict.participants
      : [];
    const childGroup = conflictResult.childGroup ?? null;

    const data: Record<string, unknown> = {
      verdict,
      rawStatus,
      participants,
      childGroup,
      winningOverride: winning.ok ? winning.result : null,
      referencedBy: referencedBy.ok ? referencedBy.result : null,
    };
    if (includeReferences) {
      data.references = referencesEnv?.ok ? referencesEnv.result : null;
    }

    const env = okEnv({
      tool: "xedit_inspect_conflicts_deep",
      summary: `verdict ${verdict} for ${String(args.formId)} (childGroup=${childGroup ? "present" : "absent"}${includeReferences ? ", refs=on" : ""})`,
      status: "completed",
      data,
      warnings: r.warnings,
    });
    await emitAudit({
      audit: opts.audit,
      tool: "xedit_inspect_conflicts_deep",
      args,
      env,
      ctx,
      ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
    });
    return env;
  };
}
