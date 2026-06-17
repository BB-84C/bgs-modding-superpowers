/**
 * NAMESAFE001 — block filesystem path syntax in name-shaped arguments.
 *
 * This is intentionally separate from PATHSAFE001: it only applies when the
 * argument key is semantically a mod/profile/title/name field, where slashes,
 * drive letters, traversal markers, Windows-forbidden filename characters,
 * and surrounding whitespace are never valid names.
 */
import { registerRule } from "../registry.js";
import { walkStringArgs } from "../arg-walk.js";
import type { Rule } from "../../types.js";

const NAME_KEY_PATTERN = /^(name|mod_name|profile|new_profile|new_name|old_name|from_profile|source|target|title|above|target_separator|label)$/i;
const FORBIDDEN_NAME_CHARS = /[<>:"|?*\\/]/;
const CONTROL_CHARS = /[\x00-\x1f]/;

function hasParentSegment(value: string): boolean {
  return value.split(/[\\/]+/).includes("..");
}

function hasUnsafeNameShape(value: string): boolean {
  return value.trim() !== value || hasParentSegment(value) || FORBIDDEN_NAME_CHARS.test(value) || CONTROL_CHARS.test(value);
}

export const nameSafetyDenyRule: Rule = {
  id: "NAMESAFE001",
  severity: "CRITICAL",
  appliesTo: () => true,
  evaluate: async (_ctx, args, _toolName) => {
    for (const arg of walkStringArgs(args)) {
      if (NAME_KEY_PATTERN.test(arg.key) && hasUnsafeNameShape(arg.value)) {
        return {
          code: "NAMESAFE001",
          severity: "CRITICAL",
          decision: "block",
          message: `Unsafe name argument forbidden at ${arg.path}: ${arg.value}`,
        };
      }
    }
    return null;
  },
};

registerRule(nameSafetyDenyRule);
