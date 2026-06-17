/**
 * PATHSAFE001 — block path traversal metacharacters anywhere in tool args.
 *
 * This is a broad value-shape guard for path-shaped arguments: every string
 * argument at any depth is denied if it carries a literal ".." path segment or
 * a NUL byte. Name-shaped arguments are left to NAMESAFE001 so unsafe names
 * receive the name-safety diagnostic instead of the path-safety diagnostic.
 */
import { registerRule } from "../registry.js";
import { walkStringArgs } from "../arg-walk.js";
const NAME_KEY_PATTERN = /^(name|mod_name|profile|new_profile|new_name|old_name|from_profile|source|target|title|above|target_separator|label)$/i;
function hasParentSegment(value) {
    return value.split(/[\\/]+/).includes("..");
}
export const pathTraversalDenyRule = {
    id: "PATHSAFE001",
    severity: "CRITICAL",
    appliesTo: () => true,
    evaluate: async (_ctx, args, _toolName) => {
        for (const arg of walkStringArgs(args)) {
            if (NAME_KEY_PATTERN.test(arg.key))
                continue;
            if (arg.value.includes("\0") || hasParentSegment(arg.value)) {
                return {
                    code: "PATHSAFE001",
                    severity: "CRITICAL",
                    decision: "block",
                    message: `Path traversal argument forbidden at ${arg.path}: ${arg.value}`,
                };
            }
        }
        return null;
    },
};
registerRule(pathTraversalDenyRule);
