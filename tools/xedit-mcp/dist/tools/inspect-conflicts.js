import { z } from "zod";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { emitAudit } from "../audit-line.js";
import { mapVerdict } from "../verdict.js";
const Args = z.object({
    file: z.string().min(1),
    // Accept both "0x0000003C" and bare "0000003C" — strip 0x before forwarding to daemon.
    formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});
/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args) {
    if (typeof args.formId !== "string")
        return args;
    const f = args.formId;
    return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}
export function makeInspectConflictsHandler(opts) {
    return async (args) => {
        const ctx = opts.getContext();
        if (!ctx) {
            // No audit logger before session context exists.
            return refuse({
                tool: "xedit_inspect_conflicts",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
        }
        const v = validateArgs(Args, args, { tool: "xedit_inspect_conflicts" });
        if (v) {
            await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts", args, env: v, ctx });
            return v;
        }
        // precheck uses daemon only; load-order owned by LOAD001 rule.
        const p = precheck({ tool: "xedit_inspect_conflicts", args }, { ctx, needs: { daemon: true } });
        if (p) {
            await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts", args, env: p, ctx });
            return p;
        }
        const r = await runRules({ tool: "xedit_inspect_conflicts", args, ctx, registry: opts.registry });
        if (r.refusal) {
            await emitAudit({
                audit: opts.audit,
                tool: "xedit_inspect_conflicts",
                args,
                env: r.refusal,
                ctx,
                ruleHits: r.ruleHits,
            });
            return r.refusal;
        }
        const daemonArgs = stripFormIdPrefix(args);
        const [conflict, winning, referencedBy] = await Promise.all([
            opts.adapter.call({ command: "records.conflict_status", args: daemonArgs }),
            opts.adapter.call({ command: "records.winning_override", args: daemonArgs }),
            opts.adapter.call({ command: "records.referenced_by", args: daemonArgs }),
        ]);
        if (!conflict.ok) {
            const env = refuse({
                tool: "xedit_inspect_conflicts",
                summary: `records.conflict_status failed: ${conflict.error.code}`,
                code: MCP_ERROR_CODES.DAEMON_ERROR,
                hint: conflict.error.message,
            });
            await emitAudit({ audit: opts.audit, tool: "xedit_inspect_conflicts", args, env, ctx });
            return env;
        }
        // The live daemon returns conflict information under `result.conflict.all`
        // (xEdit `caXxx` enum). Fall back to `result.status` for unit-test mocks that
        // still use a flat status field.
        const conflictResult = conflict.result;
        const rawStatus = String(conflictResult.conflict?.all ?? conflictResult.status ?? "unknown");
        const verdict = mapVerdict(rawStatus);
        const participants = Array.isArray(conflictResult.conflict?.participants)
            ? conflictResult.conflict.participants
            : [];
        const env = okEnv({
            tool: "xedit_inspect_conflicts",
            summary: `verdict ${verdict} for ${String(args.formId)}`,
            status: "completed",
            data: {
                verdict,
                rawStatus,
                participants,
                winningOverride: winning.ok ? winning.result : null,
                referencedBy: referencedBy.ok ? referencedBy.result : null,
            },
            warnings: r.warnings,
        });
        await emitAudit({
            audit: opts.audit,
            tool: "xedit_inspect_conflicts",
            args,
            env,
            ctx,
            ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
        });
        return env;
    };
}
//# sourceMappingURL=inspect-conflicts.js.map