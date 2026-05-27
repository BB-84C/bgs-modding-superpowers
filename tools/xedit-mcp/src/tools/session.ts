import type { DaemonAdapter } from "../daemon-adapter.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { buildContext } from "../session.js";

export interface XeditSessionToolOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export interface XeditSessionTool {
  /** The MCP tool handler. */
  tool: (args: Record<string, unknown>) => Promise<Envelope>;
  /** Access the most recently built ToolContext (for other tools to share). */
  getContext: () => ToolContext | undefined;
}

export function xeditSessionTool(opts: XeditSessionToolOptions): XeditSessionTool {
  let ctx: ToolContext | undefined;
  return {
    tool: async (_args: Record<string, unknown>): Promise<Envelope> => {
      try {
        ctx = await buildContext(opts);
        const dirtyRes = await opts.adapter.call({ command: "session.get_dirty_state", args: {} });
        const dirty = dirtyRes.ok
          ? (dirtyRes.result as {
              dirty?: boolean;
              dirtyFiles?: string[];
              unsavedChangeCount?: number;
            })
          : {};
        return okEnv({
          tool: "xedit_session",
          summary: `daemon ready (${ctx.capabilities?.gameMode ?? "?"}, ${ctx.loadOrder?.length ?? 0} files)`,
          status: "completed",
          data: {
            gameMode: ctx.capabilities?.gameMode,
            contractVersion: ctx.capabilities?.contractVersion,
            loadOrderSize: ctx.loadOrder?.length ?? 0,
            consentEnabled: !!ctx.consentEnabled,
            mcpModeActive: !!ctx.mcpModeActive,
            dirty: dirty.dirty === true,
          },
          dirty: {
            files: dirty.dirtyFiles ?? [],
            unsavedChangeCount: dirty.unsavedChangeCount ?? 0,
          },
        });
      } catch (err) {
        return refuse({
          tool: "xedit_session",
          summary: "Failed to build session context",
          code: MCP_ERROR_CODES.STATE_VIOLATION,
          hint: (err as Error).message,
        });
      }
    },
    getContext: () => ctx,
  };
}
