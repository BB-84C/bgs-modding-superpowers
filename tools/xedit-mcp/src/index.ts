import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { statSync } from "node:fs";

import type { DaemonAdapter } from "./daemon-adapter.js";
import type { Envelope } from "./types.js";
import { createAuditLogger } from "./audit.js";
import { defaultRegistry } from "./rules/registry.js";
import { xeditSessionTool } from "./tools/session.js";
import { xeditListCapabilitiesTool } from "./tools/list-capabilities.js";
import { makeFindRecordHandler } from "./tools/find-record.js";
import { makeReadRecordHandler } from "./tools/read-record.js";
import { makeInspectConflictsHandler } from "./tools/inspect-conflicts.js";
import { makeCallHandler } from "./tools/call.js";
import { refuse } from "./envelope.js";
import { MCP_ERROR_CODES } from "./types.js";
import { launchDaemon, type LaunchOptions, type LaunchedDaemon } from "./launch.js";

export interface ServerToolsetOptions {
  adapter: DaemonAdapter;
  sessionId: string;
  auditDir?: string;
  daemonPid?: number;
  mcpModeActive?: boolean;
}

export interface ServerToolset {
  list: () => string[];
  invoke: (name: string, args: Record<string, unknown>) => Promise<Envelope>;
}

export function buildServerToolset(opts: ServerToolsetOptions): ServerToolset {
  const audit = createAuditLogger({
    baseDir: opts.auditDir ?? join(tmpdir(), "xedit-mcp-audit"),
  });
  const registry = defaultRegistry();
  const session = xeditSessionTool({
    adapter: opts.adapter,
    sessionId: opts.sessionId,
    daemonPid: opts.daemonPid ?? process.pid,
    mcpModeActive: opts.mcpModeActive,
  });
  const getCtx = session.getContext;

  const listCaps = xeditListCapabilitiesTool({ adapter: opts.adapter, getContext: getCtx });
  const find = makeFindRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const read = makeReadRecordHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const inspect = makeInspectConflictsHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });
  const call = makeCallHandler({ adapter: opts.adapter, registry, audit, getContext: getCtx });

  const handlers: Record<string, (a: Record<string, unknown>) => Promise<Envelope>> = {
    xedit_session: session.tool,
    xedit_list_capabilities: listCaps,
    xedit_find_record: find,
    xedit_read_record: read,
    xedit_inspect_conflicts: inspect,
    xedit_call: call,
  };

  return {
    list: () => Object.keys(handlers),
    invoke: async (name, args) => {
      const h = handlers[name];
      if (!h) {
        return refuse({
          tool: name,
          summary: `Unknown tool: ${name}`,
          code: MCP_ERROR_CODES.INVALID_REQUEST,
          hint: "List available tools via the MCP listTools request.",
        });
      }
      return h(args);
    },
  };
}

// Production entry: stdio MCP server with lazy daemon launch.
//
// The daemon (xEdit via MO2 control-plane) is expensive to start (~60-180s) so
// we do not launch at server startup. Instead, the first tool call triggers
// launchDaemon, buildServerToolset wraps the resulting adapter, and subsequent
// calls reuse the cached toolset. The first tool call can take minutes; ensure
// the MCP client's timeout is set generously (OpenCode plugin sets 240s).
//
// Launch configuration comes from env vars (preferred) or relative auto-detect
// for the dev sandbox layout. Required for production use:
//   BGS_XEDIT_CLIENT_SCRIPT  absolute path to tools/mo2-vfs-launcher/xedit-client.ps1
//   BGS_XEDIT_LAUNCHER_PATH  absolute path to xEdit.exe (typically <MO2>/tools/xEdit/)
//   BGS_XEDIT_GAME_MODE      xEdit game mode string, e.g. "Fallout4"
//   BGS_MO2_PROFILE          optional, defaults to "Default"
//
// Pre-req for any tool call to succeed: MO2 must already be running with the
// Mo2AgentControl plugin loaded (the setting-up-bgs-modding-environment skill
// installs the plugin; the user starts MO2 themselves).

interface ResolvedLaunchOpts extends LaunchOptions {}

function resolveLaunchOpts(): ResolvedLaunchOpts | { error: string } {
  const envClient = process.env.BGS_XEDIT_CLIENT_SCRIPT;
  const envLauncher = process.env.BGS_XEDIT_LAUNCHER_PATH;
  const envGameMode = process.env.BGS_XEDIT_GAME_MODE;
  const envProfile = process.env.BGS_MO2_PROFILE ?? "Default";

  if (envClient && envLauncher && envGameMode) {
    return {
      clientScript: envClient,
      launcherPath: envLauncher,
      gameMode: envGameMode,
      moProfile: envProfile,
    };
  }

  // Auto-detect: src/index.js lives at <plugin-root>/tools/xedit-mcp/dist/index.js
  // (or src/index.ts during tests). Walk up three levels to plugin root.
  try {
    const thisFile = fileURLToPath(import.meta.url);
    const pluginRoot = resolve(dirname(thisFile), "..", "..", "..");
    const candidateClient = envClient ?? resolve(pluginRoot, "tools/mo2-vfs-launcher/xedit-client.ps1");
    const candidateLauncher = envLauncher ?? resolve(pluginRoot, ".artifacts/mo2/tools/xEdit/xEdit.exe");
    statSync(candidateClient);
    statSync(candidateLauncher);
    return {
      clientScript: candidateClient,
      launcherPath: candidateLauncher,
      gameMode: envGameMode ?? "Fallout4",
      moProfile: envProfile,
    };
  } catch {
    return {
      error:
        "xedit-mcp is not configured. Set env vars on the MCP server: " +
        "BGS_XEDIT_CLIENT_SCRIPT (path to xedit-client.ps1), " +
        "BGS_XEDIT_LAUNCHER_PATH (path to xEdit.exe), " +
        "BGS_XEDIT_GAME_MODE (e.g. 'Fallout4'). " +
        "Auto-detect fallback expects xEdit at <plugin-root>/.artifacts/mo2/tools/xEdit/xEdit.exe (dev sandbox).",
    };
  }
}

const TOOL_DEFINITIONS = [
  { name: "xedit_session", description: "Ensure daemon, return session summary (gameMode, loadOrderSize, daemonPid). Call first every conversation." },
  { name: "xedit_list_capabilities", description: "Curated 49-command digest + live drift report against the daemon." },
  { name: "xedit_find_record", description: "Locate records by {file, formId} or {editorId}." },
  { name: "xedit_read_record", description: "Composite read: record + winning override + base record + conflict status." },
  { name: "xedit_inspect_conflicts", description: "Conflict audit verdict (no_conflict / itpo / itm / minor / breaking) + winning + referencedBy." },
  { name: "xedit_call", description: "Atomic passthrough for any of the 49 native daemon commands. Still traverses the full harness pipeline. Use when an intent tool does not fit." },
].map((t) => ({ ...t, inputSchema: { type: "object" as const, additionalProperties: true } }));

export async function main(): Promise<void> {
  const server = new Server(
    { name: "xedit-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  let cachedToolset: ServerToolset | null = null;
  let cachedDaemon: LaunchedDaemon | null = null;
  let cachedFatal: string | null = null;
  let inflightLaunch: Promise<ServerToolset | { error: string }> | null = null;

  async function ensureToolset(): Promise<ServerToolset | { error: string }> {
    if (cachedToolset) return cachedToolset;
    if (cachedFatal) return { error: cachedFatal };
    if (inflightLaunch) return inflightLaunch;

    inflightLaunch = (async () => {
      const opts = resolveLaunchOpts();
      if ("error" in opts) {
        cachedFatal = opts.error;
        return opts;
      }
      try {
        cachedDaemon = await launchDaemon(opts);
        cachedToolset = buildServerToolset({
          adapter: cachedDaemon.adapter,
          sessionId: `mcp-${process.pid}-${Date.now()}`,
          daemonPid: cachedDaemon.pid,
        });
        return cachedToolset;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        // Do NOT cache transient launch failures (e.g., MO2 not running yet);
        // let the next tool call retry.
        return { error: `Daemon launch failed: ${msg}` };
      } finally {
        inflightLaunch = null;
      }
    })();

    return inflightLaunch;
  }

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const name = req.params.name;
    const args = (req.params.arguments ?? {}) as Record<string, unknown>;

    const tsOrErr = await ensureToolset();
    if ("error" in tsOrErr) {
      const envelope = {
        ok: false,
        tool: name,
        code: "launch_failed",
        summary: tsOrErr.error,
        hint: tsOrErr.error,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(envelope) }],
        isError: true,
      };
    }

    try {
      const envelope = await tsOrErr.invoke(name, args);
      return {
        content: [{ type: "text", text: JSON.stringify(envelope) }],
        isError: !envelope.ok,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        content: [{
          type: "text",
          text: JSON.stringify({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }),
        }],
        isError: true,
      };
    }
  });

  const shutdown = async (signal: string) => {
    process.stderr.write(`xedit-mcp received ${signal}, shutting down...\n`);
    if (cachedDaemon) {
      try { await cachedDaemon.stop(); } catch { /* best effort */ }
    }
    process.exit(0);
  };
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  await server.connect(new StdioServerTransport());
}

// Detect "invoked as the main entry" cross-platform.
// On Windows the naive `file://${argv[1]}` form has backslashes and only 2
// slashes, while import.meta.url is forward-slash + 3 slashes — string compare
// never matches and main() silently no-ops, causing MCP hosts to see a
// connection-closed (-32000) on startup. Use pathToFileURL to normalize.
const invokedAsMain = (() => {
  const argv = process.argv[1];
  if (!argv) return false;
  try {
    return import.meta.url === pathToFileURL(argv).href;
  } catch {
    return false;
  }
})();

if (invokedAsMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
