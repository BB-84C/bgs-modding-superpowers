import { createHash } from "node:crypto";
import type { AuditLogger } from "./audit.js";
import type { Envelope, ToolContext, Warning } from "./types.js";

/**
 * Shared per-tool audit emitter.
 *
 * Stage [7] of the pipeline (audit + envelope) requires every MCP tool call to
 * emit exactly one append-only JSONL line. Historically `read-record.ts` and
 * `inspect-conflicts.ts` each carried a local `auditLine` helper, while
 * `session.ts` and `list-capabilities.ts` skipped audit entirely, and
 * `inspect`'s payload omitted `daemonPid` / `sessionId`. This module is the
 * single source of truth so every tool's audit line carries the same fields.
 *
 * Contract:
 * - Best-effort. Audit append errors are swallowed by `AuditLogger` itself.
 * - `decision` is derived from the envelope: ok -> "ok", refused/!ok -> "refused".
 *   Callers that want to mark a successful envelope that carried warnings as
 *   "warned" can override `decision` explicitly.
 * - `argsHash` is a 16-char sha256 prefix; unhashable args fall back to
 *   "unhashable" rather than throw.
 * - `daemonPid` / `sessionId` are pulled from `ctx` when present.
 */
export interface EmitAuditOptions {
  audit: AuditLogger;
  tool: string;
  args: Record<string, unknown>;
  env: Envelope;
  ctx?: ToolContext;
  /** Optional explicit override for decision (e.g. "warned" for an ok+warnings envelope). */
  decision?: "ok" | "refused" | "warned";
  /** Optional rule-hit IDs (e.g. ["LOAD001"]) — surfaces in the audit line. */
  ruleHits?: string[];
}

export async function emitAudit(opts: EmitAuditOptions): Promise<void> {
  const decision: "ok" | "refused" | "warned" =
    opts.decision ?? (opts.env.ok ? (warningCount(opts.env.warnings) > 0 ? "warned" : "ok") : "refused");
  await opts.audit.append({
    tool: opts.tool,
    argsHash: hashArgs(opts.args),
    decision,
    ok: opts.env.ok,
    code: opts.env.ok ? undefined : opts.env.code,
    ruleHits: opts.ruleHits,
    daemonPid: opts.ctx?.daemonPid,
    sessionId: opts.ctx?.sessionId,
  });
}

function warningCount(warnings: Warning[] | undefined): number {
  return Array.isArray(warnings) ? warnings.length : 0;
}

export function hashArgs(args: Record<string, unknown>): string {
  try {
    return createHash("sha256").update(JSON.stringify(args)).digest("hex").slice(0, 16);
  } catch {
    return "unhashable";
  }
}
