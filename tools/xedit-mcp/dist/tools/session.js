import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { buildContext } from "../session.js";
import { emitAudit } from "../audit-line.js";
export function xeditSessionTool(opts) {
    let ctx;
    return {
        tool: async (args) => {
            let env;
            try {
                ctx = await buildContext(opts);
                const dirtyRes = await opts.adapter.call({ command: "session.get_dirty_state", args: {} });
                const dirty = dirtyRes.ok
                    ? dirtyRes.result
                    : {};
                env = okEnv({
                    tool: "xedit_session",
                    summary: `daemon ready (${ctx.capabilities?.gameMode ?? "?"}, ${ctx.loadOrder?.length ?? 0} files)`,
                    status: "completed",
                    data: {
                        gameMode: ctx.capabilities?.gameMode,
                        contractVersion: ctx.capabilities?.contractVersion,
                        loadOrderSize: ctx.loadOrder?.length ?? 0,
                        consentEnabled: !!ctx.consentEnabled,
                        mcpModeActive: !!ctx.mcpModeActive,
                        dirty: dirty.dirty === true,
                    },
                    dirty: {
                        files: dirty.dirtyFiles ?? [],
                        unsavedChangeCount: dirty.unsavedChangeCount ?? 0,
                    },
                });
            }
            catch (err) {
                env = refuse({
                    tool: "xedit_session",
                    summary: "Failed to build session context",
                    code: MCP_ERROR_CODES.STATE_VIOLATION,
                    hint: err.message,
                });
            }
            if (opts.audit) {
                // Use the real ctx when buildContext succeeded; otherwise synthesize the
                // minimal { sessionId, daemonPid } from opts so the audit line still
                // carries the lifecycle identifiers for the failed call.
                const auditCtx = ctx ?? { sessionId: opts.sessionId, daemonPid: opts.daemonPid };
                await emitAudit({ audit: opts.audit, tool: "xedit_session", args, env, ctx: auditCtx });
            }
            return env;
        },
        getContext: () => ctx,
    };
}
//# sourceMappingURL=session.js.map