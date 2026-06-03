import { createHash } from "node:crypto";
export async function emitAudit(opts) {
    const decision = opts.decision ?? (opts.env.ok ? (warningCount(opts.env.warnings) > 0 ? "warned" : "ok") : "refused");
    await opts.audit.append({
        tool: opts.tool,
        argsHash: hashArgs(opts.args),
        decision,
        ok: opts.env.ok,
        code: opts.env.ok ? undefined : opts.env.code,
        ruleHits: opts.ruleHits,
        daemonPid: opts.ctx?.daemonPid,
        sessionId: opts.ctx?.sessionId,
    });
}
function warningCount(warnings) {
    return Array.isArray(warnings) ? warnings.length : 0;
}
export function hashArgs(args) {
    try {
        return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
    }
    catch {
        return "unhashable";
    }
}
//# sourceMappingURL=audit-line.js.map