import type { AuditLogger } from "./audit.js";
import type { DaemonAdapter, NativeEnvelope } from "./daemon-adapter.js";
import { refuse, ok } from "./envelope.js";
import { hashArgs } from "./audit-line.js";
import type { PendingSaveTracker } from "./pending-save.js";
import { MCP_ERROR_CODES, type Envelope, type ToolContext } from "./types.js";

export interface FlushSummary {
  status: "completed" | "partial";
  outcome: "known" | "unknown";
  force: boolean;
  flushed: { attempted: number; renamed: number; failed: number };
  pendingRemaining: string[];
  pendingRemainingCount: number;
  daemonExited: boolean;
  at: string;
  daemonPid?: number;
}

export interface FlushHandlerOptions {
  adapter: DaemonAdapter;
  tracker: PendingSaveTracker;
  waitForExit: (timeoutMs: number) => Promise<boolean>;
  onConfirmedExit: (summary: FlushSummary) => void;
  onExitFailure: (message: string, summary?: FlushSummary) => void;
  getContext: () => ToolContext | undefined;
  audit: AuditLogger;
  exitTimeoutMs?: number;
}

export interface RetryFailedFlushExitOptions {
  waitForExit: (timeoutMs: number) => Promise<boolean>;
  tracker: PendingSaveTracker;
  lastFlush: FlushSummary;
  onConfirmedExit: (summary: FlushSummary) => void;
  timeoutMs?: number;
}

export async function retryFailedFlushExit(
  opts: RetryFailedFlushExitOptions,
): Promise<FlushSummary | null> {
  if (opts.lastFlush.daemonExited) return opts.lastFlush;
  let exited = false;
  try {
    exited = await opts.waitForExit(opts.timeoutMs ?? 1_000);
  } catch {
    return null;
  }
  if (!exited) return null;
  const updated: FlushSummary = { ...opts.lastFlush, daemonExited: true };
  opts.tracker.clearForSessionTransition();
  opts.onConfirmedExit(updated);
  return updated;
}

export function makeFlushHandler(opts: FlushHandlerOptions) {
  return async (rawArgs: Record<string, unknown>): Promise<Envelope> => {
    const force = rawArgs.force === true;
    const nativeArgs = Object.prototype.hasOwnProperty.call(rawArgs, "force") ? { force } : {};
    const ctx = opts.getContext();
    const auditBase = {
      tool: "xedit_flush",
      argsHash: hashArgs(rawArgs),
      force,
      daemonPid: ctx?.daemonPid,
      sessionId: ctx?.sessionId,
    };

    let capabilities: NativeEnvelope;
    try {
      capabilities = await opts.adapter.call({ command: "system.capabilities", args: {} });
    } catch (error) {
      const message = errorMessage(error);
      const env = refuse({
        tool: "xedit_flush",
        summary: "Could not verify session.flush support",
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: message,
      });
      await opts.audit.append({ ...auditBase, decision: "refused", ok: false, code: env.code, daemonExited: false });
      return env;
    }
    if (!capabilities.ok) {
      const env = refuse({
        tool: "xedit_flush",
        summary: `session.flush capability probe failed: ${capabilities.error.message}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: "The daemon returned an error to system.capabilities; lifecycle state was left unchanged.",
        detail: daemonErrorDetail(capabilities.error),
      });
      await opts.audit.append({ ...auditBase, decision: "refused", ok: false, code: env.code, daemonExited: false });
      return env;
    }
    const supportsFlush = isRecord(capabilities.result)
      && isRecord(capabilities.result.supports)
      && capabilities.result.supports.sessionFlush === true;
    if (!supportsFlush) {
      const env = refuse({
        tool: "xedit_flush",
        summary: "The loaded xEdit daemon does not advertise session.flush",
        code: MCP_ERROR_CODES.UNSUPPORTED_BY_DAEMON,
        hint: "Use an xEdit automation daemon implementing contract 0.23 with supports.sessionFlush=true.",
      });
      await opts.audit.append({ ...auditBase, decision: "refused", ok: false, code: env.code, daemonExited: false });
      return env;
    }

    let flushEnvelope: NativeEnvelope;
    try {
      flushEnvelope = await opts.adapter.call({ command: "session.flush", args: nativeArgs });
    } catch (error) {
      return settleTransportFailure(error, auditBase, opts);
    }

    if (!flushEnvelope.ok) {
      if (flushEnvelope.error.code === "consent_required" || flushEnvelope.error.code === "state_conflict") {
        const env = refuse({
          tool: "xedit_flush",
          summary: flushEnvelope.error.message,
          code: flushEnvelope.error.code === "consent_required"
            ? MCP_ERROR_CODES.CONSENT_REQUIRED
            : MCP_ERROR_CODES.STATE_CONFLICT,
          hint: flushEnvelope.error.message,
          detail: daemonErrorDetail(flushEnvelope.error),
        });
        await opts.audit.append({ ...auditBase, decision: "refused", ok: false, code: env.code, daemonExited: false });
        return env;
      }
      return settleDaemonFailure(flushEnvelope, auditBase, opts);
    }

    const parsedResult = parseFlushResult(flushEnvelope.result);
    if (!parsedResult.ok) {
      return settleTransportFailure(
        new Error(`flush result malformed: ${parsedResult.reason}`),
        auditBase,
        opts,
      );
    }
    const { result, flushedFiles, pendingRemaining, pendingRemainingCount } = parsedResult;
    const renamed = flushedFiles.filter((entry) => isRecord(entry) && entry.renamed === true).length;
    const failed = flushedFiles.length - renamed;
    const partial = failed > 0 || pendingRemainingCount > 0;
    opts.tracker.observePostFlushRemaining(pendingRemaining, pendingRemainingCount);
    const postDrainPending = opts.tracker.snapshot();
    const baseSummary: FlushSummary = {
      // Lifecycle completion still depends on the promised daemon self-exit.
      status: "partial",
      outcome: "known",
      force,
      flushed: { attempted: flushedFiles.length, renamed, failed },
      pendingRemaining,
      pendingRemainingCount,
      daemonExited: false,
      at: new Date().toISOString(),
      daemonPid: auditBase.daemonPid,
    };
    const exited = await safeWaitForExit(opts);
    if (!exited) {
      const message = "session.flush returned, but the managed daemon did not confirm exit before the bounded timeout";
      opts.onExitFailure(message, baseSummary);
      const env = refuse({
        tool: "xedit_flush",
        summary: message,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: "The runtime remains attached for explicit lifecycle handling; no automatic stop or kill was attempted.",
        detail: {
          flushed: baseSummary.flushed,
          pendingRemaining,
          pendingRemainingCount,
          lastFlush: baseSummary,
        },
      });
      await opts.audit.append({
        ...auditBase,
        decision: "refused",
        ok: false,
        code: env.code,
        flushed: { attempted: flushedFiles.length, renamed, failed },
        pendingRemaining: pendingRemainingCount,
        pendingShutdownSave: postDrainPending,
        daemonExited: false,
        flushOutcome: "known",
        risk: "flush_exit_unconfirmed",
      });
      return env;
    }

    const summary: FlushSummary = {
      ...baseSummary,
      status: partial ? "partial" : "completed",
      daemonExited: true,
    };
    // Never feed result.dirtyState into the tracker: the contract defines it as
    // the pre-drain snapshot. Confirmed process exit clears the blocking guard.
    opts.tracker.clearForSessionTransition();
    opts.onConfirmedExit(summary);
    const env = ok({
      tool: "xedit_flush",
      summary: partial ? "Daemon exited after an incomplete pending-rename drain" : "Pending renames drained and daemon exit confirmed",
      status: summary.status,
      data: {
        ...result,
        daemonExited: true,
        lastFlush: summary,
        ...(partial
          ? { nextStep: "Failed renames remain queued for retry during daemon exit; use a fresh daemon readback before deciding durability." }
          : {}),
      },
      warnings: partial
        ? [{
            code: "FLUSH_INCOMPLETE",
            message: "One or more renames failed in-band and remain queued for retry during daemon exit; only a fresh-daemon readback can establish durability.",
            severity: "HIGH",
          }]
        : [],
    });
    await opts.audit.append({
      ...auditBase,
      decision: partial ? "warned" : "ok",
      ok: true,
      flushed: summary.flushed,
      pendingRemaining: pendingRemainingCount,
      pendingShutdownSave: postDrainPending,
      daemonExited: true,
      flushOutcome: "known",
    });
    return env;
  };
}

async function settleTransportFailure(
  error: unknown,
  auditBase: Pick<import("./audit.js").AuditRecord, "tool" | "argsHash" | "force" | "daemonPid" | "sessionId">,
  opts: FlushHandlerOptions,
): Promise<Envelope> {
  const message = errorMessage(error);
  const priorPending = opts.tracker.snapshot();
  const priorNames = pendingFileNames(priorPending.files);
  const exited = await safeWaitForExit(opts);
  const summary = unknownFlushSummary(auditBase, priorNames, priorPending.count, exited);
  if (exited) {
    opts.tracker.clearForSessionTransition();
    opts.onConfirmedExit(summary);
  } else opts.onExitFailure(message, summary);
  const env = refuse({
    tool: "xedit_flush",
    summary: exited
      ? `session.flush outcome unknown; process exit confirmed: ${message}`
      : `session.flush transport failed and process exit was not confirmed: ${message}`,
    code: MCP_ERROR_CODES.DAEMON_ERROR,
    hint: exited
      ? "Flush outcome unknown; process exit confirmed. Blocking pending-save state was cleared, while prior pending knowledge remains in lastFlush residue."
      : "Daemon exit was not confirmed; runtime state is failed and retained for explicit lifecycle handling.",
  });
  await opts.audit.append({
    ...auditBase,
    decision: "refused",
    ok: false,
    code: env.code,
    risk: "flush_outcome_unknown",
    pendingRemaining: priorPending.count,
    pendingShutdownSave: priorPending,
    daemonExited: exited,
    flushOutcome: "unknown",
  });
  return env;
}

async function settleDaemonFailure(
  flushEnvelope: Extract<NativeEnvelope, { ok: false }>,
  auditBase: Pick<import("./audit.js").AuditRecord, "tool" | "argsHash" | "force" | "daemonPid" | "sessionId">,
  opts: FlushHandlerOptions,
): Promise<Envelope> {
  const priorPending = opts.tracker.snapshot();
  const message = `${flushEnvelope.error.code}: ${flushEnvelope.error.message}`;
  const exited = await safeWaitForExit(opts);
  if (exited) {
    const summary = unknownFlushSummary(
      auditBase,
      pendingFileNames(priorPending.files),
      priorPending.count,
      true,
    );
    opts.tracker.clearForSessionTransition();
    opts.onConfirmedExit(summary);
    const env = refuse({
      tool: "xedit_flush",
      summary: `session.flush outcome unknown; process exit confirmed: ${message}`,
      code: MCP_ERROR_CODES.DAEMON_ERROR,
      hint: "Flush outcome unknown; process exit confirmed. Prior pending knowledge remains in lastFlush residue for fresh-daemon readback.",
      detail: daemonErrorDetail(flushEnvelope.error),
    });
    await opts.audit.append({
      ...auditBase,
      decision: "refused",
      ok: false,
      code: env.code,
      risk: "flush_outcome_unknown",
      pendingRemaining: priorPending.count,
      pendingShutdownSave: priorPending,
      daemonExited: true,
      flushOutcome: "unknown",
    });
    return env;
  }

  const env = refuse({
    tool: "xedit_flush",
    summary: flushEnvelope.error.message,
    code: MCP_ERROR_CODES.DAEMON_ERROR,
    hint: "The daemon returned a structured error and remained alive; lifecycle state was left ready.",
    detail: daemonErrorDetail(flushEnvelope.error),
  });
  await opts.audit.append({
    ...auditBase,
    decision: "refused",
    ok: false,
    code: env.code,
    pendingShutdownSave: priorPending,
    daemonExited: false,
  });
  return env;
}

function unknownFlushSummary(
  auditBase: Pick<import("./audit.js").AuditRecord, "force" | "daemonPid">,
  pendingRemaining: string[],
  pendingRemainingCount: number,
  daemonExited: boolean,
): FlushSummary {
  return {
    status: "partial",
    outcome: "unknown",
    force: auditBase.force === true,
    flushed: { attempted: 0, renamed: 0, failed: 0 },
    pendingRemaining,
    pendingRemainingCount,
    daemonExited,
    at: new Date().toISOString(),
    daemonPid: auditBase.daemonPid,
  };
}

async function safeWaitForExit(opts: FlushHandlerOptions): Promise<boolean> {
  try {
    return await opts.waitForExit(opts.exitTimeoutMs ?? 30_000);
  } catch {
    return false;
  }
}

function validCount(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : undefined;
}

type FlushFileResult = Record<string, unknown> & { fileName: string; renamed: boolean };

type ParsedFlushResult =
  | {
      ok: true;
      result: Record<string, unknown>;
      flushedFiles: FlushFileResult[];
      pendingRemaining: string[];
      pendingRemainingCount: number;
    }
  | { ok: false; reason: string };

function parseFlushResult(value: unknown): ParsedFlushResult {
  if (!isRecord(value)) return { ok: false, reason: "result must be an object" };
  if (!Array.isArray(value.flushedFiles)) {
    return { ok: false, reason: "flushedFiles must be an array" };
  }
  const flushedFiles: FlushFileResult[] = [];
  for (let index = 0; index < value.flushedFiles.length; index += 1) {
    const entry = value.flushedFiles[index];
    if (!isRecord(entry)) {
      return { ok: false, reason: `flushedFiles[${index}] must be an object` };
    }
    if (typeof entry.fileName !== "string" || entry.fileName.length === 0) {
      return { ok: false, reason: `flushedFiles[${index}].fileName must be a non-empty string` };
    }
    if (typeof entry.renamed !== "boolean") {
      return { ok: false, reason: `flushedFiles[${index}].renamed must be boolean` };
    }
    flushedFiles.push(entry as FlushFileResult);
  }

  if (!Array.isArray(value.pendingRemaining)) {
    return { ok: false, reason: "pendingRemaining must be an array" };
  }
  if (!value.pendingRemaining.every((entry) => typeof entry === "string")) {
    return { ok: false, reason: "pendingRemaining must contain only strings" };
  }
  const pendingRemaining = value.pendingRemaining as string[];
  const pendingRemainingCount = validCount(value.pendingRemainingCount);
  if (pendingRemainingCount === undefined) {
    return { ok: false, reason: "pendingRemainingCount must be a non-negative integer" };
  }
  if (pendingRemainingCount !== pendingRemaining.length) {
    return {
      ok: false,
      reason: `pendingRemainingCount (${pendingRemainingCount}) must equal pendingRemaining.length (${pendingRemaining.length})`,
    };
  }
  return { ok: true, result: value, flushedFiles, pendingRemaining, pendingRemainingCount };
}

function pendingFileNames(files: unknown[]): string[] {
  const names: string[] = [];
  for (const entry of files) {
    const name = pendingFileName(entry);
    if (name) names.push(name);
  }
  return names;
}

function pendingFileName(value: unknown): string | undefined {
  if (typeof value === "string" && value.length > 0) return value;
  if (!isRecord(value)) return undefined;
  if (typeof value.fileName === "string" && value.fileName.length > 0) return value.fileName;
  if (typeof value.name === "string" && value.name.length > 0) return value.name;
  return isRecord(value.file) ? pendingFileName(value.file) : undefined;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function daemonErrorDetail(error: { code: string; details?: unknown }): Record<string, unknown> {
  return {
    nativeCode: error.code,
    ...(isRecord(error.details) ? { nativeDetails: error.details } : {}),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
