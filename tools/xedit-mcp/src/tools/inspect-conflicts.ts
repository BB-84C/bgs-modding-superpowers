import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";

const Args = z.object({
  file: z.string().min(1),
  // Accept both "0x0000003C" and bare "0000003C" — strip 0x before forwarding to daemon.
  formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});

/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args: Record<string, unknown>): Record<string, unknown> {
  if (typeof args.formId !== "string") return args;
  const f = args.formId;
  return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}

export type Verdict = "no_conflict" | "itpo" | "itm" | "minor" | "breaking";

export interface InspectConflictsOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeInspectConflictsHandler(opts: InspectConflictsOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_inspect_conflicts",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }

    const v = validateArgs(Args, args, { tool: "xedit_inspect_conflicts" });
    if (v) return v;

    // precheck uses daemon only; load-order owned by LOAD001 rule.
    const p = precheck({ tool: "xedit_inspect_conflicts", args }, { ctx, needs: { daemon: true } });
    if (p) return p;

    const r = await runRules({ tool: "xedit_inspect_conflicts", args, ctx, registry: opts.registry });
    if (r) return r;

    const daemonArgs = stripFormIdPrefix(args);
    const [conflict, winning, referencedBy] = await Promise.all([
      opts.adapter.call({ command: "records.conflict_status", args: daemonArgs }),
      opts.adapter.call({ command: "records.winning_override", args: daemonArgs }),
      opts.adapter.call({ command: "records.referenced_by", args: daemonArgs }),
    ]);

    if (!conflict.ok) {
      return refuse({
        tool: "xedit_inspect_conflicts",
        summary: `records.conflict_status failed: ${conflict.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: conflict.error.message,
      });
    }

    const status = String((conflict.result as { status?: string }).status ?? "unknown");
    const verdict: Verdict = mapVerdict(status);

    return okEnv({
      tool: "xedit_inspect_conflicts",
      summary: `verdict ${verdict} for ${String(args.formId)}`,
      status: "completed",
      data: {
        verdict,
        rawStatus: status,
        winningOverride: winning.ok ? winning.result : null,
        referencedBy: referencedBy.ok ? referencedBy.result : null,
      },
    });
  };
}

function mapVerdict(status: string): Verdict {
  const s = status.toLowerCase();
  if (s.includes("itpo")) return "itpo";
  if (s.includes("itm")) return "itm";
  if (s === "no_conflict" || s === "no conflict") return "no_conflict";
  if (s.includes("critical") || s.includes("breaking")) return "breaking";
  if (s.includes("conflict")) return "minor";
  return "minor";
}
