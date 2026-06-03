import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { CAPABILITIES_DIGEST, allDigestCommands } from "../capabilities-digest.js";
import { emitAudit } from "../audit-line.js";

export interface XeditListCapabilitiesOptions {
  adapter: DaemonAdapter;
  getContext: () => ToolContext | undefined;
  /** Optional. When present, every xedit_list_capabilities call emits an audit line. */
  audit?: AuditLogger;
}

export function xeditListCapabilitiesTool(
  opts: XeditListCapabilitiesOptions,
): (args: Record<string, unknown>) => Promise<Envelope> {
  return async (args) => {
    const ctx = opts.getContext();
    let env: Envelope;
    if (!ctx?.capabilities) {
      env = refuse({
        tool: "xedit_list_capabilities",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    } else {
      const live = new Set(ctx.capabilities.commands);
      const digest = new Set(allDigestCommands());
      const onlyInLive = [...live].filter((c) => !digest.has(c)).sort();
      const onlyInDigest = [...digest].filter((c) => !live.has(c)).sort();

      env = okEnv({
        tool: "xedit_list_capabilities",
        summary: `Digest ${digest.size} commands, live ${live.size}; drift ${onlyInLive.length + onlyInDigest.length}`,
        status: "completed",
        data: {
          contractVersion: ctx.capabilities.contractVersion,
          contractVersionExpected: CAPABILITIES_DIGEST.contractVersionExpected,
          gameMode: ctx.capabilities.gameMode,
          groups: CAPABILITIES_DIGEST.groups,
          drift: { onlyInDigest, onlyInLive },
        },
      });
    }
    if (opts.audit) {
      await emitAudit({ audit: opts.audit, tool: "xedit_list_capabilities", args, env, ctx });
    }
    return env;
  };
}
