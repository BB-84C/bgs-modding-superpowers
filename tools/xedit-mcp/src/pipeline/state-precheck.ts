import type { EnvelopeRefusal, ToolContext } from "../types.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

export interface PrecheckNeeds {
  daemon?: boolean;
  consent?: boolean;
  /** Name of the args field whose string value must be present in ctx.loadOrder. */
  targetFileFromArg?: string;
}

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

  if (needs.targetFileFromArg) {
    const file = (call.args ?? {})[needs.targetFileFromArg];
    if (typeof file === "string" && !(ctx.loadOrder ?? []).includes(file)) {
      return refuse({
        tool: call.tool,
        summary: `Target file not in active load order: ${file}`,
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Add the file to plugins.txt (active load order) and reload the session first.",
        detail: { file, loadOrder: ctx.loadOrder ?? [] },
      });
    }
  }

  return null;
}
