import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { buildContext } from "../session.js";
export function xeditSessionTool(opts) {
    let ctx;
    return {
        tool: async (_args) => {
            try {
                ctx = await buildContext(opts);
                const dirtyRes = await opts.adapter.call({ command: "session.get_dirty_state", args: {} });
                const dirty = dirtyRes.ok
                    ? dirtyRes.result
                    : {};
                return okEnv({
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
                return refuse({
                    tool: "xedit_session",
                    summary: "Failed to build session context",
                    code: MCP_ERROR_CODES.STATE_VIOLATION,
                    hint: err.message,
                });
            }
        },
        getContext: () => ctx,
    };
}
//# sourceMappingURL=session.js.map