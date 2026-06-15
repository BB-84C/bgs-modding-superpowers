/**
 * CEILING001 — enforce configured permission_ceiling against registered tool tier.
 *
 * Allow matrix:
 *   T1: read-only, metadata-editable, full-control
 *   T2: metadata-editable, full-control
 *   T3: full-control only
 */
import { getTool } from "../../tool-registry.js";
import { registerRule } from "../registry.js";
import type { Config } from "../../config.js";
import type { Rule } from "../../types.js";

type ToolTier = "T1" | "T2" | "T3";
type PermissionCeiling = Config["permissionCeiling"];

const CEILING_RANK: Record<PermissionCeiling, number> = {
  "read-only": 0,
  "metadata-editable": 1,
  "full-control": 2,
};

const REQUIRED_BY_TIER: Record<ToolTier, PermissionCeiling> = {
  T1: "read-only",
  T2: "metadata-editable",
  T3: "full-control",
};

export const permissionCeilingRule: Rule = {
  id: "CEILING001",
  severity: "CRITICAL",
  appliesTo: (toolName) => getTool(toolName) !== undefined,
  evaluate: async (ctx, _args, toolName) => {
    const tool = getTool(toolName);
    if (!tool) return null;

    const required = REQUIRED_BY_TIER[tool.tier];
    const configured = ctx.config.permissionCeiling;
    if (CEILING_RANK[configured] >= CEILING_RANK[required]) return null;

    return {
      code: "CEILING001",
      severity: "CRITICAL",
      decision: "block",
      message:
        `Tool ${tool.name} requires permission_ceiling >= ${required}, current is ${configured}. ` +
        "Set permission_ceiling in .mo2-mcp.json or env BGS_MO2_PERMISSION_CEILING.",
      tier: tool.tier,
      required_ceiling: required,
      configured_ceiling: configured,
    };
  },
};

registerRule(permissionCeilingRule);
