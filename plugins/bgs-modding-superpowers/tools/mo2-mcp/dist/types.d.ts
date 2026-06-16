/**
 * Shared types used across MCP server modules.
 */
import type { Config } from "./config.js";
import type { BindingManager } from "./binding.js";
import type { PlanCache } from "./plan-apply.js";
import type { SnapshotManager } from "./snapshot.js";
import type { AuditLogger } from "./audit.js";
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM";
export type RuleDecision = "pass" | "warn" | "block";
export interface RuleFinding {
    code: string;
    severity: Severity;
    decision: RuleDecision;
    message: string;
    data?: unknown;
    tier?: "T1" | "T2" | "T3";
    required_ceiling?: Config["permissionCeiling"];
    configured_ceiling?: Config["permissionCeiling"];
}
export interface ToolContext {
    binding: BindingManager;
    sessionId: string;
    plans: PlanCache;
    snapshots: SnapshotManager;
    audit: AuditLogger;
}
export interface Rule {
    id: string;
    severity: Severity;
    appliesTo: (toolName: string) => boolean;
    evaluate: (ctx: ToolContext, args: Record<string, unknown>, toolName: string) => Promise<RuleFinding | null>;
}
