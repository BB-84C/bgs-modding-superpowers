/**
 * BrokerEnrichedError + classification helpers.
 *
 * Lane B of ENRICHMENT-DESIGN.md. Carries structured failure info from
 * pipe-client to dispatch's catch branch so the agent-facing envelope can
 * include MO2 process responsiveness + mo2.log tail instead of just an
 * opaque "pipe call timeout" message.
 *
 * Correction 3 of BATCH1-CORRECTIONS.md: dispatch.ts (`dispatch.ts:166-198`)
 * only reads `e.message` for the generic internal_error fallback, dropping
 * structured `code` and `details`. A typed subclass lets dispatch route this
 * shape into a structured envelope without losing context.
 */
import { probeMo2Process, type Mo2ProcessState } from "./mo2-process-state.js";
import { tailMo2Log } from "./mo2-log.js";

export class BrokerEnrichedError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;
  constructor(args: { code: string; message: string; details: Record<string, unknown> }) {
    super(args.message);
    this.name = "BrokerEnrichedError";
    this.code = args.code;
    this.details = args.details;
  }
}

export interface ClassifiedError {
  code: string;
  message: string;
  hint?: string;
}

/**
 * Pure classification of a broker failure given the original raw error message
 * and the MO2 process responsiveness state. Exposed for unit tests; the
 * `enrichBrokerError` wrapper drives the live probe + log-tail calls around
 * this helper.
 *
 * Priority: a non-responding MO2 GUI overrides everything else, because the
 * underlying pipe/timeout/parse-error symptom is downstream of the modal
 * dialog blocking the Qt main thread (BUG-16). When MO2 is responding (or
 * the process is gone), we fall back to message-prefix classification of the
 * original raw error.
 */
export function _classifyError(originalMessage: string, procState: Mo2ProcessState): ClassifiedError {
  if (procState.alive && procState.responding === false) {
    return {
      code: "mo2_gui_unresponsive",
      message:
        "MO2 main thread is not responding — likely a modal dialog or long-running operation blocking the GUI",
      hint: "Check MO2 window for a modal dialog and dismiss it, or restart MO2",
    };
  }
  if (originalMessage.startsWith("pipe call timeout")) {
    return { code: "pipe_call_timeout", message: originalMessage };
  }
  if (originalMessage.startsWith("empty pipe response")) {
    return { code: "pipe_empty_response", message: originalMessage };
  }
  if (originalMessage.startsWith("pipe response parse error")) {
    return { code: "pipe_parse_error", message: originalMessage };
  }
  return { code: "broker_error", message: originalMessage };
}

/**
 * Wrap a raw broker failure with L1 process state + L2 log tail, then build
 * a typed BrokerEnrichedError for dispatch.ts to surface as a structured
 * envelope. Always returns a BrokerEnrichedError (never throws) so the caller
 * can `throw enrichBrokerError(...)` without a second try/catch.
 *
 * `startedAt` is the call's start time (Date.now()); used to seed the log
 * tail's sinceTs filter so we don't drown the agent in pre-call log noise.
 */
export async function enrichBrokerError(
  err: unknown,
  method: string,
  mo2Root: string,
  startedAt: number,
): Promise<BrokerEnrichedError> {
  const originalMessage = err instanceof Error ? err.message : String(err);
  const procState = await probeMo2Process(mo2Root).catch(() => ({ alive: false } as Mo2ProcessState));
  const tail = await tailMo2Log(mo2Root, {
    sinceTs: new Date(startedAt - 1000),
    maxLines: 30,
  }).catch(() => ({ lines: [], truncated: false, logPath: "" }));

  const classified = _classifyError(originalMessage, procState);
  const details: Record<string, unknown> = {
    method,
    originalMessage,
    processState: procState,
  };
  if (tail.lines.length > 0) {
    details.mo2_log_tail = { lines: tail.lines, truncated: tail.truncated, logPath: tail.logPath };
  }
  if (classified.hint) {
    details.hint = classified.hint;
  }

  return new BrokerEnrichedError({
    code: classified.code,
    message: classified.message,
    details,
  });
}
