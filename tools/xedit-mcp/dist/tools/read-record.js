import { createHash } from "node:crypto";
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
export function makeReadRecordHandler(opts) {
    return async (args) => {
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
            await auditLine(opts, "xedit_read_record", args, v, ctx);
            return v;
        }
        // NOTE: precheck uses `daemon` only; load-order is owned by LOAD001 rule.
        const p = precheck({ tool: "xedit_read_record", args }, { ctx, needs: { daemon: true } });
        if (p) {
            await auditLine(opts, "xedit_read_record", args, p, ctx);
            return p;
        }
        const r = await runRules({ tool: "xedit_read_record", args, ctx, registry: opts.registry });
        if (r) {
            await auditLine(opts, "xedit_read_record", args, r, ctx);
            return r;
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
            await auditLine(opts, "xedit_read_record", args, env, ctx);
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
        });
        await auditLine(opts, "xedit_read_record", args, env, ctx);
        return env;
    };
}
async function auditLine(opts, tool, args, env, ctx) {
    await opts.audit.append({
        tool,
        argsHash: safeHashArgs(args),
        decision: env.ok ? "ok" : "refused",
        ok: env.ok,
        code: env.ok ? undefined : env.code,
        daemonPid: ctx.daemonPid,
        sessionId: ctx.sessionId,
    });
}
function safeHashArgs(args) {
    try {
        return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
    }
    catch {
        return "unhashable";
    }
}
//# sourceMappingURL=read-record.js.map