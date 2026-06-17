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
import { type Mo2ProcessState } from "./mo2-process-state.js";
export declare class BrokerEnrichedError extends Error {
    readonly code: string;
    readonly details: Record<string, unknown>;
    constructor(args: {
        code: string;
        message: string;
        details: Record<string, unknown>;
    });
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
export declare function _classifyError(originalMessage: string, procState: Mo2ProcessState): ClassifiedError;
/**
 * Wrap a raw broker failure with L1 process state + L2 log tail, then build
 * a typed BrokerEnrichedError for dispatch.ts to surface as a structured
 * envelope. Always returns a BrokerEnrichedError (never throws) so the caller
 * can `throw enrichBrokerError(...)` without a second try/catch.
 *
 * `startedAt` is the call's start time (Date.now()); used to seed the log
 * tail's sinceTs filter so we don't drown the agent in pre-call log noise.
 */
export declare function enrichBrokerError(err: unknown, method: string, mo2Root: string, startedAt: number): Promise<BrokerEnrichedError>;
