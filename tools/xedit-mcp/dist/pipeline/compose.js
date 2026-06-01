import { createHash } from "node:crypto";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "./validate.js";
import { precheck } from "./state-precheck.js";
import { runRules } from "./rules.js";
import { forwardCall } from "./forward.js";
export async function runTool(spec, input) {
    const argsHash = safeHashArgs(input.args);
    try {
        const meta = { tool: spec.name };
        const v = validateArgs(spec.schema, input.args, meta);
        if (v) {
            await input.audit.append({ tool: spec.name, argsHash, decision: "refused", ok: false, code: v.code });
            return v;
        }
        const p = precheck({ tool: spec.name, args: input.args }, { ctx: input.ctx, needs: spec.needs });
        if (p) {
            await input.audit.append({ tool: spec.name, argsHash, decision: "refused", ok: false, code: p.code });
            return p;
        }
        const r = await runRules({ tool: spec.name, args: input.args, ctx: input.ctx, registry: input.registry });
        if (r) {
            await input.audit.append({
                tool: spec.name, argsHash, decision: "refused", ok: false, code: r.code,
                ruleHits: [r.code.replace(/^rule_/, "")],
            });
            return r;
        }
        const env = await forwardCall({
            tool: spec.name,
            command: spec.command,
            args: input.args,
            adapter: input.adapter,
            summary: spec.summary(input.args),
            shape: spec.shape,
        });
        await input.audit.append({
            tool: spec.name, argsHash, decision: env.ok ? "ok" : "refused", ok: env.ok,
            code: env.ok ? undefined : env.code,
            daemonPid: input.ctx.daemonPid, sessionId: input.ctx.sessionId,
        });
        return env;
    }
    catch (err) {
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
            tool: spec.name, argsHash, decision: "refused", ok: false, code: refusal.code,
            daemonPid: input.ctx.daemonPid, sessionId: input.ctx.sessionId,
        });
        return refusal;
    }
}
function safeHashArgs(args) {
    try {
        return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
    }
    catch {
        return "unhashable";
    }
}
//# sourceMappingURL=compose.js.map