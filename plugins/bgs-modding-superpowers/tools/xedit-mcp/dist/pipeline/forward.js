import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
export async function forwardCall(input) {
    const native = await input.adapter.call({ command: input.command, args: input.args });
    if (native.ok) {
        return okEnv({
            tool: input.tool,
            summary: input.summary,
            data: input.shape ? input.shape(native.result) : native.result,
            status: "completed",
        });
    }
    if (native.error.code === "mcp_mode_required") {
        return refuse({
            tool: input.tool,
            summary: "Daemon refused: MCP-only mode active, token required",
            code: MCP_ERROR_CODES.MCP_MODE_REQUIRED,
            hint: "The daemon is in MCP-only mode. Ensure the MCP server provisioned a valid token at launch.",
            detail: { daemonMessage: native.error.message },
        });
    }
    return refuse({
        tool: input.tool,
        summary: `Daemon error: ${native.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: native.error.message,
        detail: { daemonCode: native.error.code, daemonDetails: native.error.details },
    });
}
//# sourceMappingURL=forward.js.map