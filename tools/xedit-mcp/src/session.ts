import type { DaemonAdapter } from "./daemon-adapter.js";
import type { ToolContext, CapabilitiesSnapshot } from "./types.js";

export interface BuildContextOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export async function buildContext(opts: BuildContextOptions): Promise<ToolContext> {
  const { adapter, sessionId } = opts;

  const describeRes = await adapter.call({ command: "system.describe", args: {} });
  const capsRes = await adapter.call({ command: "system.capabilities", args: {} });
  const filesRes = await adapter.call({ command: "files.list", args: {} });

  const describe = describeRes.ok ? (describeRes.result as Record<string, unknown>) : {};
  const caps = capsRes.ok ? (capsRes.result as Record<string, unknown>) : {};
  const files = filesRes.ok ? (filesRes.result as { files?: string[] }) : { files: [] };

  const supports = (caps.supports ?? {}) as Record<string, unknown>;

  const capabilities: CapabilitiesSnapshot = {
    contractVersion: String(caps.contractVersion ?? "unknown"),
    gameMode: String(describe.gameMode ?? "unknown"),
    commands: Array.isArray(caps.commands) ? (caps.commands as string[]) : [],
    supports,
    fetchedAt: new Date().toISOString(),
  };

  return {
    sessionId,
    daemonPid: opts.daemonPid,
    mcpModeActive: opts.mcpModeActive ?? false,
    loadOrder: files.files ?? [],
    consentEnabled: supports.iKnowWhatImDoing === true,
    capabilities,
  };
}
