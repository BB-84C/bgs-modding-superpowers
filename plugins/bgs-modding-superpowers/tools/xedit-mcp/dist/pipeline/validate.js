import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
export function validateArgs(schema, args, meta = { tool: "unknown" }) {
    const result = schema.safeParse(args);
    if (result.success)
        return null;
    const issues = result.error.issues.map((i) => ({
        path: i.path.join("."),
        expected: i.message,
        code: i.code,
    }));
    return refuse({
        tool: meta.tool,
        summary: "Argument validation failed",
        code: MCP_ERROR_CODES.INVALID_REQUEST,
        hint: "Fix the listed fields and retry.",
        detail: { issues },
    });
}
//# sourceMappingURL=validate.js.map