/**
 * PATHSAFE001 — block path traversal metacharacters anywhere in tool args.
 *
 * This is a broad value-shape guard: every string argument at any depth is
 * denied if it carries a literal ".." path segment or a NUL byte.
 */
import { registerRule } from "../registry.js";
import { walkStringArgs } from "../arg-walk.js";
import type { Rule } from "../../types.js";

function hasParentSegment(value: string): boolean {
  return value.split(/[\\/]+/).includes("..");
}

export const pathTraversalDenyRule: Rule = {
  id: "PATHSAFE001",
  severity: "CRITICAL",
  appliesTo: () => true,
  evaluate: async (_ctx, args) => {
    for (const arg of walkStringArgs(args)) {
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
