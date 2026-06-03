export const MCP_ERROR_CODES = {
  INVALID_REQUEST: "invalid_request",
  STATE_VIOLATION: "state_violation",
  DAEMON_ERROR: "daemon_error",
  INTERNAL_ERROR: "internal_error",
  MCP_MODE_REQUIRED: "mcp_mode_required",
  SNAPSHOT_FAILED: "snapshot_failed",
  CONFIRM_REQUIRED: "confirm_required",
  CONFIRM_TOKEN_INVALID: "confirm_token_invalid",
  CONFIRM_TOKEN_EXPIRED: "confirm_token_expired",
} as const;

export type McpErrorCode =
  | (typeof MCP_ERROR_CODES)[keyof typeof MCP_ERROR_CODES]
  | `rule_${string}`;

export type Severity = "MEDIUM" | "HIGH" | "CRITICAL";

export interface Warning {
  code: string;
  message: string;
  severity: "MEDIUM" | "HIGH";
}

export interface ChangedSet {
  files: string[];
  records: string[];
  counts: { added: number; modified: number; deleted: number };
}

export type EnvelopeStatus =
  | "completed"
  | "pending_shutdown"
  | "partial"
  | "preview"
  | "refused";

export interface EnvelopeBase {
  tool: string;
  summary: string;
  warnings: Warning[];
}

export interface EnvelopeOk extends EnvelopeBase {
  ok: true;
  data?: unknown;
  changed?: ChangedSet;
  status?: Exclude<EnvelopeStatus, "refused">;
  snapshotId?: string;
  dirty?: { files: string[]; unsavedChangeCount: number };
  readback?: { kind: "snapshot" | "resource"; ref: string };
  preview?: { from: unknown; to: unknown; affected: unknown[] };
  confirmToken?: string;
  expiresAt?: string;
}

export interface EnvelopeRefusal extends EnvelopeBase {
  ok: false;
  code: McpErrorCode;
  status?: "refused";
  severity?: Severity;
  hint?: string;
  rationale?: string;
  matched?: Record<string, unknown>;
  detail?: Record<string, unknown>;
}

export type Envelope = EnvelopeOk | EnvelopeRefusal;

export interface Finding {
  ruleId: string;
  matched: Record<string, unknown>;
  message: string;
}

export interface ToolContext {
  daemonPid?: number;
  loadOrder?: string[];
  consentEnabled?: boolean;
  mcpModeActive?: boolean;
  capabilities?: CapabilitiesSnapshot;
  /** Session id used for audit + future snapshot pathing. */
  sessionId: string;
}

export interface CapabilitiesSnapshot {
  contractVersion: string;
  gameMode: string;
  commands: string[];
  supports?: Record<string, unknown>;
  fetchedAt: string;
}

export interface Rule {
  id: string;
  appliesTo: string[];
  riskLevel: Severity;
  description: string;
  suggestion: string;
  rationale?: string;
  check: (input: {
    tool: string;
    args: Record<string, unknown>;
    ctx: ToolContext;
  }) => Finding | null;
}
