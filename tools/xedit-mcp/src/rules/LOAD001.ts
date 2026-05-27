import type { Rule } from "../types.js";

export const LOAD001: Rule = {
  id: "LOAD001",
  appliesTo: [
    "xedit_find_record",
    "xedit_read_record",
    "xedit_inspect_conflicts",
    "xedit_call",
  ],
  riskLevel: "CRITICAL",
  description: "Target file is not in the active load order.",
  suggestion: "Add the file to plugins.txt and reload the session first.",
  rationale:
    "Operations against an unloaded file silently miss records and produce false-negative conflict reports.",
  check({ args, ctx }) {
    const file = typeof args.file === "string" ? args.file : undefined;
    if (!file) return null;
    const loadOrder = ctx.loadOrder ?? [];
    if (loadOrder.includes(file)) return null;
    return {
      ruleId: "LOAD001",
      matched: { file, loadOrderSize: loadOrder.length },
      message: `File ${file} not in load order`,
    };
  },
};
