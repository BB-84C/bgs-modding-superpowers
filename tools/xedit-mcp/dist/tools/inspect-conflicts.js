import { z } from "zod";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
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
            const env = refuse({
                tool: "xedit_inspect_conflicts",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
            // No audit logger before session context exists.
            return env;
        }
        const v = validateArgs(Args, args, { tool: "xedit_inspect_conflicts" });
        if (v) {
            await auditLine(opts, "xedit_inspect_conflicts", args, v);
            return v;
        }
        // precheck uses daemon only; load-order owned by LOAD001 rule.
        const p = precheck({ tool: "xedit_inspect_conflicts", args }, { ctx, needs: { daemon: true } });
        if (p) {
            await auditLine(opts, "xedit_inspect_conflicts", args, p);
            return p;
        }
        const r = await runRules({ tool: "xedit_inspect_conflicts", args, ctx, registry: opts.registry });
        if (r) {
            await auditLine(opts, "xedit_inspect_conflicts", args, r);
            return r;
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
            await auditLine(opts, "xedit_inspect_conflicts", args, env);
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
        });
        await auditLine(opts, "xedit_inspect_conflicts", args, env);
        return env;
    };
}
async function auditLine(opts, tool, args, env) {
    await opts.audit.append({
        tool,
        argsHash: simpleHash(args),
        decision: env.ok ? "ok" : "refused",
        ok: env.ok,
        code: env.ok ? undefined : env.code,
    });
}
function simpleHash(args) {
    let h = 0;
    const s = JSON.stringify(args);
    for (let i = 0; i < s.length; i++)
        h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h).toString(16);
}
/**
 * Map xEdit's conflict-all enum (or legacy flat status strings) to MCP verdict.
 *
 * xEdit conflict-all enum (from `records.conflict_status` -> `result.conflict.all`):
 *  - caUnknown / caOnlyOne / caNoConflict   -> no_conflict
 *  - caITM                                  -> itm   (identical to master)
 *  - caITPO                                 -> itpo  (identical to previous override)
 *  - caOverride / caConflictBenign          -> minor (override present, content benign)
 *  - caConflict                             -> minor (real semantic conflict)
 *  - caConflictCritical                     -> breaking
 *
 * Legacy flat string statuses (e.g. unit-test mocks that send "no_conflict",
 * "conflict_critical", "ITPO") are still recognized.
 */
function mapVerdict(status) {
    const s = status.toLowerCase();
    if (s === "caitpo" || s.includes("itpo"))
        return "itpo";
    if (s === "caitm" || s.includes("itm"))
        return "itm";
    if (s === "caunknown" ||
        s === "caonlyone" ||
        s === "canoconflict" ||
        s === "no_conflict" ||
        s === "no conflict") {
        return "no_conflict";
    }
    if (s === "caconflictcritical" || s.includes("critical") || s.includes("breaking")) {
        return "breaking";
    }
    if (s === "caoverride" || s === "caconflictbenign")
        return "minor";
    if (s === "caconflict")
        return "minor";
    if (s.includes("conflict"))
        return "minor";
    return "minor";
}
//# sourceMappingURL=inspect-conflicts.js.map