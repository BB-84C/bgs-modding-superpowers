import type { EnvelopeRefusal, ToolContext } from "../types.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

export interface PrecheckNeeds {
  daemon?: boolean;
  consent?: boolean;
}

/**
 * Stage [2] of the harness pipeline — fast structural state checks before
 * rules run.
 *
 * Batch 2 (carry-forward #5): The pre-Batch-2 design also carried a
 * `targetFileFromArg` option that refused if a named args field's string
 * value was not in `ctx.loadOrder`. It is intentionally retired here.
 *
 * Rationale:
 *  - Load-order enforcement is owned by the rule layer (LOAD001) so every
 *    record-side tool gets the same refusal shape with full
 *    suggestion + rationale on the envelope, not a bare state_violation.
 *  - After find-record stopped using it (Batch 2), there were zero remaining
 *    consumers; keeping the field would be dead surface area that future
 *    contributors could mistake for the canonical load-order seam.
 *  - If a future write-side tool wants a hard pre-rule load-order short-circuit,
 *    add a focused `targetFileLoaded(needs, args, ctx)` helper or a HIGH-severity
 *    rule — both are clearer than a precheck option whose existence implies
 *    parallel load-order enforcement at two layers.
 */
export function precheck(
  call: { tool: string; args?: Record<string, unknown> },
  input: { ctx: ToolContext; needs: PrecheckNeeds },
): EnvelopeRefusal | null {
  const { ctx, needs } = input;

  if (needs.daemon && !ctx.daemonPid) {
    return refuse({
      tool: call.tool,
      summary: "Daemon not ready",
      code: MCP_ERROR_CODES.STATE_VIOLATION,
      hint: "Call xedit_session first to ensure the daemon is running.",
    });
  }

  if (needs.consent && !ctx.consentEnabled) {
    return refuse({
      tool: call.tool,
      summary: "Consent flag not active",
      code: MCP_ERROR_CODES.STATE_VIOLATION,
      hint: "Relaunch daemon with -IKnowWhatImDoing to enable mutating ops.",
    });
  }

  return null;
}
