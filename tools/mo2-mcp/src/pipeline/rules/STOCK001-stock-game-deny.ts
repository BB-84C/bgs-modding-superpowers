/**
 * STOCK001 — hard-deny any path mutation under Stock Game/Data.
 *
 * Maps to project-local memory `70-stock-game-protection.md`: writes to
 * <MO2_Root>/Stock Game/Data are forbidden; use MO2 overlay under mods/ instead.
 *
 * Applies to ALL tools (read-only tools won't carry such paths, so they no-op).
 */
import { registerRule } from "../registry.js";
import type { Rule } from "../../types.js";

const DENY_PATTERN = /Stock Game[/\\]Data[/\\]/i;

export const stockGameDenyRule: Rule = {
  id: "STOCK001",
  severity: "CRITICAL",
  appliesTo: () => true,
  evaluate: async (_ctx, args) => {
    const candidates = [
      args.path,
      args.virtual_path,
      args.archive_path,
      args.target_path,
      args.ini_path,
    ].filter((value): value is string => typeof value === "string");

    for (const path of candidates) {
      if (DENY_PATTERN.test(path)) {
        return {
          code: "STOCK001",
          severity: "CRITICAL",
          decision: "block",
          message: `Stock Game/Data path mutation forbidden: ${path} (use MO2 overlay under mods/)`,
        };
      }
    }
    return null;
  },
};

registerRule(stockGameDenyRule);
