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

  const [describeRes, capsRes, filesRes] = await Promise.all([
    adapter.call({ command: "system.describe", args: {} }),
    adapter.call({ command: "system.capabilities", args: {} }),
    adapter.call({ command: "files.list", args: {} }),
  ]);

  const describe = describeRes.ok ? (describeRes.result as Record<string, unknown>) : {};
  const caps = capsRes.ok ? (capsRes.result as Record<string, unknown>) : {};
  const filesResult = filesRes.ok ? (filesRes.result as { files?: unknown }) : {};
  const loadOrder = Array.isArray(filesResult.files)
    ? (filesResult.files as unknown[]).filter((f): f is string => typeof f === "string")
    : [];

  const supports = (caps.supports ?? {}) as Record<string, unknown>;

  const capabilities: CapabilitiesSnapshot = {
    contractVersion: String(caps.contractVersion ?? "unknown"),
    // Prefer the friendly `gameName` ("Fallout4") over the internal `gameMode`
    // token ("gmFO4"). Fall back to gameMode for adapters/tests that only set
    // the latter (e.g. the existing unit test mock).
    gameMode: String(describe.gameName ?? describe.gameMode ?? "unknown"),
    commands: Array.isArray(caps.commands) ? (caps.commands as string[]) : [],
    supports,
    fetchedAt: new Date().toISOString(),
  };

  return {
    sessionId,
    daemonPid: opts.daemonPid,
    mcpModeActive: opts.mcpModeActive ?? false,
    loadOrder,
    consentEnabled: supports.iKnowWhatImDoing === true,
    capabilities,
  };
}
