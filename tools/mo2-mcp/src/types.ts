/**
 * Shared types used across MCP server modules.
 */
import type { Config } from "./config.js";
import type { PipeClient } from "./pipe-client.js";
import type { SidecarClient } from "./sidecar-client.js";

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM";
export type RuleDecision = "pass" | "warn" | "block";

export interface RuleFinding {
  code: string;
  severity: Severity;
  decision: RuleDecision;
  message: string;
  data?: unknown;
}

export interface ToolContext {
  config: Config;
  pipeClient?: PipeClient;
  sidecar?: SidecarClient;
  sessionId: string;
  // S2.10/11/12/13 add: plans, snapshots, audit, lease verifier.
}

export interface Rule {
  id: string;
  severity: Severity;
  appliesTo: (toolName: string) => boolean;
  evaluate: (ctx: ToolContext, args: Record<string, unknown>) => Promise<RuleFinding | null>;
}
