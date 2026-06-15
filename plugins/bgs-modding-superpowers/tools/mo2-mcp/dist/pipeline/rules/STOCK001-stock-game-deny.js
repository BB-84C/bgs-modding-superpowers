/**
 * STOCK001 — hard-deny any argument string that points under Stock Game/<game>/Data.
 *
 * Maps to project-local memory `70-stock-game-protection.md`: writes to
 * <MO2_Root>/Stock Game/<game>/Data are forbidden; use MO2 overlay under mods/ instead.
 *
 * Applies to ALL tools and walks args recursively so nested plan/choice payloads
 * cannot bypass the guard by using an unlisted argument key.
 */
import { registerRule } from "../registry.js";
import { walkStringArgs } from "../arg-walk.js";
const DENY_PATTERNS = [
    /Stock Game[/\\](?:[^/\\]+[/\\])?Data(?:[/\\]|$)/i,
];
export const stockGameDenyRule = {
    id: "STOCK001",
    severity: "CRITICAL",
    appliesTo: () => true,
    evaluate: async (_ctx, args, _toolName) => {
        for (const arg of walkStringArgs(args)) {
            if (DENY_PATTERNS.some((pattern) => pattern.test(arg.value))) {
                return {
                    code: "STOCK001",
                    severity: "CRITICAL",
                    decision: "block",
                    message: `Stock Game/Data path mutation forbidden at ${arg.path}: ${arg.value} (use MO2 overlay under mods/)`,
                };
            }
        }
        return null;
    },
};
registerRule(stockGameDenyRule);
