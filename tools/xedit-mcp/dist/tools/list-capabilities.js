import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { CAPABILITIES_DIGEST, allDigestCommands } from "../capabilities-digest.js";
export function xeditListCapabilitiesTool(opts) {
    return async (_args) => {
        const ctx = opts.getContext();
        if (!ctx?.capabilities) {
            return refuse({
                tool: "xedit_list_capabilities",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
        }
        const live = new Set(ctx.capabilities.commands);
        const digest = new Set(allDigestCommands());
        const onlyInLive = [...live].filter((c) => !digest.has(c)).sort();
        const onlyInDigest = [...digest].filter((c) => !live.has(c)).sort();
        return okEnv({
            tool: "xedit_list_capabilities",
            summary: `Digest ${digest.size} commands, live ${live.size}; drift ${onlyInLive.length + onlyInDigest.length}`,
            status: "completed",
            data: {
                contractVersion: ctx.capabilities.contractVersion,
                contractVersionExpected: CAPABILITIES_DIGEST.contractVersionExpected,
                gameMode: ctx.capabilities.gameMode,
                groups: CAPABILITIES_DIGEST.groups,
                drift: { onlyInDigest, onlyInLive },
            },
        });
    };
}
//# sourceMappingURL=list-capabilities.js.map