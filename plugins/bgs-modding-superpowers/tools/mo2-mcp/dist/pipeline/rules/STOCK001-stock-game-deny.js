/**
 * STOCK001 — hard-deny protected game-data roots and user deny patterns.
 *
 * Historical note: the rule ID/file name came from this repo's original
 * private harness convention ("Stock Game"). Current semantics are general:
 * protect the game Data directory derived from ModOrganizer.ini [General]
 * gamePath, plus explicit user deny substrings from .mo2-mcp.json.
 *
 * Applies to ALL tools and walks args recursively so nested plan/choice payloads
 * cannot bypass the guard by using an unlisted argument key.
 */
import { join } from "node:path";
import { registerRule } from "../registry.js";
import { walkStringArgs } from "../arg-walk.js";
import { readMoIni } from "../../mo-ini.js";
const gameDataRootByMo2Root = new Map();
function normalizePathish(value) {
    return value.replace(/\\/g, "/").replace(/\/+$/g, "").toLowerCase();
}
function containsPathRoot(value, root) {
    const normalizedValue = normalizePathish(value);
    const normalizedRoot = normalizePathish(root);
    let index = normalizedValue.indexOf(normalizedRoot);
    while (index !== -1) {
        const next = normalizedValue[index + normalizedRoot.length];
        if (next === undefined || next === "/")
            return true;
        index = normalizedValue.indexOf(normalizedRoot, index + 1);
    }
    return false;
}
function userDenyPatternFor(value, patterns) {
    const normalizedValue = normalizePathish(value);
    for (const pattern of patterns) {
        const normalizedPattern = normalizePathish(pattern.trim());
        if (normalizedPattern && normalizedValue.includes(normalizedPattern))
            return pattern;
    }
    return null;
}
function gameDataRootFor(mo2Root) {
    let cached = gameDataRootByMo2Root.get(mo2Root);
    if (!cached) {
        cached = readMoIni(join(mo2Root, "ModOrganizer.ini"))
            .then((ini) => {
            const gamePath = ini.general.gamePath?.trim();
            return gamePath ? `${gamePath.replace(/[\\/]+$/g, "")}/Data` : null;
        })
            .catch(() => null);
        gameDataRootByMo2Root.set(mo2Root, cached);
    }
    return cached;
}
export const stockGameDenyRule = {
    id: "STOCK001",
    severity: "CRITICAL",
    appliesTo: () => true,
    evaluate: async (ctx, args, _toolName) => {
        const gameDataRoot = await gameDataRootFor(ctx.config.mo2Root);
        for (const arg of walkStringArgs(args)) {
            if (gameDataRoot && containsPathRoot(arg.value, gameDataRoot)) {
                return {
                    code: "STOCK001",
                    severity: "CRITICAL",
                    decision: "block",
                    message: `game_data_root path mutation forbidden at ${arg.path}: ${arg.value} (use MO2 overlay under mods/)`,
                    data: {
                        source: "game_data_root",
                        arg_path: arg.path,
                        game_data_root: gameDataRoot,
                    },
                };
            }
            const pattern = userDenyPatternFor(arg.value, ctx.config.deny);
            if (pattern) {
                return {
                    code: "STOCK001",
                    severity: "CRITICAL",
                    decision: "block",
                    message: `user_deny_pattern: ${pattern} matched at ${arg.path}: ${arg.value}`,
                    data: {
                        source: "user_deny_pattern",
                        pattern,
                        arg_path: arg.path,
                    },
                };
            }
        }
        return null;
    },
};
registerRule(stockGameDenyRule);
