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

// =============================================================================
// Production stdio MCP server: NON-BLOCKING state machine.
// =============================================================================
//
// Why non-blocking: launching xEdit through MO2's control plane takes 60-180s
// because xEdit has to parse the active load order before its automation-serve
// pipe answers. If tool calls block on that, every MCP client hits its turn
// timeout and the agent sees a wall of errors. Instead, the server tracks
// the daemon's lifecycle in memory and ALL tool calls return immediately.
//
// Tool surface (9 total):
//
//   LIFECYCLE / HEALTH (3)
//     xedit_status   pure read — returns { status: "not_started" | "starting" | "ready" | "failed", ... }
//                    Never blocks. Never modifies state. Use this to poll.
//     xedit_start    if not_started/failed: kick off background launch.
//                    Returns immediately with current status.
//     xedit_health   when ready: send system.ping through the named pipe to
//                    confirm the daemon is still responsive (vs zombie).
//                    Otherwise: returns the same shape as xedit_status.
//
//   DOMAIN TOOLS (6)
//     xedit_session            non-blocking. If status=ready: returns the rich
//                              session envelope. If status=not_started: auto-
//                              kicks-off launch. Otherwise: returns current
//                              status + hint to poll xedit_status.
//     xedit_list_capabilities  status=ready required, otherwise fast-fail with
//     xedit_find_record        code "not_ready". The fast-fail envelope carries
//     xedit_read_record        the current status so the agent knows whether to
//     xedit_inspect_conflicts  poll or kick off a launch.
//     xedit_call
//
// Launch configuration:
//   Env vars (preferred):
//     BGS_XEDIT_CLIENT_SCRIPT  absolute path to tools/mo2-vfs-launcher/xedit-client.ps1
//     BGS_XEDIT_LAUNCHER_PATH  absolute path to xEdit.exe (typically <MO2>/tools/xEdit/)
//     BGS_XEDIT_GAME_MODE      xEdit game mode string, e.g. "Fallout4"
//     BGS_MO2_PROFILE          optional, defaults to "Default"
//   Auto-detect fallback (dev sandbox layout):
//     <plugin-root>/tools/mo2-vfs-launcher/xedit-client.ps1
//     <plugin-root>/.artifacts/mo2/tools/xEdit/xEdit.exe
//
// Pre-req for any successful launch: MO2 must already be running with the
// Mo2AgentControl Python plugin loaded. The setting-up-bgs-modding-environment
// skill installs the Python plugin and launches MO2 visibly via
// scripts/start-mo2.ps1.

interface ResolvedLaunchOpts extends LaunchOptions {}

interface LaunchOverrides {
  launcherPath?: string;
  gameMode?: string;
  dataPath?: string;
  pluginsFile?: string;
  moProfile?: string;
}

function resolveLaunchOpts(overrides: LaunchOverrides = {}): ResolvedLaunchOpts | { error: string } {
  const envClient = process.env.BGS_XEDIT_CLIENT_SCRIPT;
  const envLauncher = process.env.BGS_XEDIT_LAUNCHER_PATH;
  const envGameMode = process.env.BGS_XEDIT_GAME_MODE;
  const envProfile = process.env.BGS_MO2_PROFILE ?? "Default";
  const envDataPath = process.env.BGS_XEDIT_DATA_PATH;
  const envPluginsFile = process.env.BGS_XEDIT_PLUGINS_FILE;

  // Resolution priority: explicit overrides (from xedit_start args) > env vars > auto-detect.
  const launcherPath = overrides.launcherPath ?? envLauncher;
  const gameMode = overrides.gameMode ?? envGameMode;
  const moProfile = overrides.moProfile ?? envProfile;
  const dataPath = overrides.dataPath ?? envDataPath;
  const pluginsFile = overrides.pluginsFile ?? envPluginsFile;

  if (envClient && launcherPath && gameMode) {
    return {
      clientScript: envClient,
      launcherPath,
      gameMode,
      moProfile,
      dataPath,
      pluginsFile,
    };
  }

  try {
    const thisFile = fileURLToPath(import.meta.url);
    const pluginRoot = resolve(dirname(thisFile), "..", "..", "..");
    const candidateClient = envClient ?? resolve(pluginRoot, "tools/mo2-vfs-launcher/xedit-client.ps1");
    const candidateLauncher = launcherPath ?? resolve(pluginRoot, ".artifacts/mo2/tools/xEdit/xEdit.exe");
    statSync(candidateClient);
    statSync(candidateLauncher);
    return {
      clientScript: candidateClient,
      launcherPath: candidateLauncher,
      gameMode: gameMode ?? "Fallout4",
      moProfile,
      dataPath,
      pluginsFile,
    };
  } catch {
    return {
      error:
        "xedit-mcp is not configured. Set env vars on the MCP server: " +
        "BGS_XEDIT_CLIENT_SCRIPT (path to xedit-client.ps1), " +
        "BGS_XEDIT_LAUNCHER_PATH (path to xEdit.exe), " +
        "BGS_XEDIT_GAME_MODE (e.g. 'Fallout4'). " +
        "Optional: BGS_XEDIT_DATA_PATH (-D: flag, MO2 Data dir), BGS_XEDIT_PLUGINS_FILE (-P: flag). " +
        "Auto-detect fallback expects xEdit at <plugin-root>/.artifacts/mo2/tools/xEdit/xEdit.exe (dev sandbox). " +
        "Or pass these as xedit_start({ launcherPath, gameMode, dataPath, pluginsFile, moProfile }) overrides at runtime.",
    };
  }
}

const TOOL_DEFINITIONS = [
  { name: "xedit_status", description: "Returns the current xEdit daemon lifecycle state without blocking. status is one of 'not_started' | 'starting' | 'ready' | 'failed'. Use this to poll while waiting for a launch." },
  { name: "xedit_start", description: "Kicks off an asynchronous xEdit daemon launch (if not already starting/ready). Returns immediately with the current status. Optional args override the env-var defaults: { launcherPath?: string (xEdit.exe), gameMode?: string ('Fallout4' etc.), dataPath?: string (-D: Data dir; pass MO2's <gamePath>\\Data to avoid xEdit's registry-discovered Steam path), pluginsFile?: string (-P: custom plugins.txt; defaults to MO2 profile), moProfile?: string ('Default' etc.) }. Reads MO2 ModOrganizer.ini gamePath via the setting-up-bgs-modding-environment skill for the canonical dataPath." },
  { name: "xedit_health", description: "When the daemon is ready, sends system.ping through the named pipe to confirm it is still responsive (catches zombie daemons). Otherwise returns the same shape as xedit_status." },
  { name: "xedit_dirty", description: "Returns xEdit's dirty state immediately. When ready: wraps session.get_dirty_state and returns { dirty, dirtyFiles, unsavedChangeCount }. Otherwise: returns the same shape as xedit_status." },
  { name: "xedit_stop", description: "Stops the xEdit daemon and clears MCP state. Before shutdown it checks session.get_dirty_state. If there are unsaved changes and force!==true, returns code='dirty_state' with dirtyFiles instead of stopping. If the daemon is a zombie, use force:true to abandon unsaved work and clear the state." },
  { name: "xedit_restart", description: "Stops the current daemon (same dirty-state safety as xedit_stop) and immediately kicks off a fresh asynchronous launch. Accepts the same overrides as xedit_start plus force?: boolean. Use this to reboot with a new pluginsFile or dataPath instead of reconnecting /mcp manually." },
  { name: "xedit_session", description: "Non-blocking. If the daemon is ready: returns gameMode, loadOrderSize, daemonPid. If not_started: auto-initiates launch. Otherwise: returns current status + hint to poll xedit_status." },
  { name: "xedit_list_capabilities", description: "Requires the daemon to be ready. Returns the curated 49-command digest + live drift report. Fast-fails with code='not_ready' otherwise." },
  { name: "xedit_find_record", description: "Requires the daemon to be ready. Locates records by {file, formId} or {editorId}. Fast-fails with code='not_ready' otherwise." },
  { name: "xedit_read_record", description: "Requires the daemon to be ready. Composite read: record + winning override + base record + conflict status. Fast-fails with code='not_ready' otherwise." },
  { name: "xedit_inspect_conflicts", description: "Requires the daemon to be ready. Conflict audit verdict + winning + referencedBy. Fast-fails with code='not_ready' otherwise." },
  { name: "xedit_call", description: "Requires the daemon to be ready. Atomic passthrough for any native daemon command, still in-harness. Fast-fails with code='not_ready' otherwise." },
].map((t) => ({ ...t, inputSchema: { type: "object" as const, additionalProperties: true } }));

// State machine
type LaunchState =
  | { status: "not_started" }
  | { status: "starting"; startedAt: number }
  | { status: "ready"; pid: number; since: number }
  | { status: "failed"; error: string; at: number };

// Helper to build the MCP CallTool response. Return type is loose so the
// SDK's expected ServerResult shape is satisfied without import-coupling.
function jsonResult(body: unknown, isError = false) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(body) }],
    isError,
  };
}

function statusFields(state: LaunchState, daemon: LaunchedDaemon | null): Record<string, unknown> {
  const out: Record<string, unknown> = { status: state.status };
  if (state.status === "starting") {
    out.startedAt = state.startedAt;
    out.elapsedSeconds = Math.round((Date.now() - state.startedAt) / 1000);
  } else if (state.status === "ready") {
    out.pid = state.pid;
    out.readySince = state.since;
    if (daemon) out.daemonPid = daemon.pid;
  } else if (state.status === "failed") {
    out.error = state.error;
    out.failedAt = state.at;
  }
  return out;
}

export async function main(): Promise<void> {
  const server = new Server(
    { name: "xedit-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  let state: LaunchState = { status: "not_started" };
  let toolset: ServerToolset | null = null;
  let daemonRef: LaunchedDaemon | null = null;
  let launchGeneration = 0;

  function clearRuntimeState(next: LaunchState = { status: "not_started" }) {
    launchGeneration += 1;
    state = next;
    toolset = null;
    daemonRef = null;
  }

  async function getDirtyState() {
    if (state.status !== "ready" || !daemonRef) {
      return {
        ok: false as const,
        body: {
          ok: true,
          tool: "xedit_dirty",
          data: { ...statusFields(state, daemonRef), responsive: false },
          hint:
            state.status === "not_started"
              ? "Daemon not started. Call xedit_start."
              : state.status === "starting"
                ? "Daemon still starting. Poll xedit_status."
                : "Daemon failed to start; inspect data.error.",
        },
      };
    }

    try {
      const env = await daemonRef.adapter.call({ command: "session.get_dirty_state", args: {} });
      if (!env.ok) {
        const code = env.error?.code ?? "daemon_error";
        const message = env.error?.message ?? "session.get_dirty_state failed";
        return {
          ok: false as const,
          body: {
            ok: false,
            tool: "xedit_dirty",
            code,
            summary: message,
            hint: message,
          },
        };
      }

      const result = (env.result ?? {}) as {
        dirty?: unknown;
        dirtyFiles?: unknown;
        unsavedChangeCount?: unknown;
      };
      const dirtyFiles = Array.isArray(result.dirtyFiles)
        ? result.dirtyFiles.filter((x): x is string => typeof x === "string")
        : [];
      const unsavedChangeCount =
        typeof result.unsavedChangeCount === "number" && Number.isFinite(result.unsavedChangeCount)
          ? result.unsavedChangeCount
          : dirtyFiles.length;

      return {
        ok: true as const,
        body: {
          ok: true,
          tool: "xedit_dirty",
          data: {
            ...statusFields(state, daemonRef),
            dirty: result.dirty === true,
            dirtyFiles,
            unsavedChangeCount,
          },
        },
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        ok: false as const,
        body: {
          ok: false,
          tool: "xedit_dirty",
          code: "daemon_error",
          summary: msg,
          hint: msg,
        },
      };
    }
  }

  function kickoffLaunch(overrides: LaunchOverrides = {}): { kicked: boolean; reason?: string } {
    if (state.status === "starting") return { kicked: false, reason: "already_starting" };
    if (state.status === "ready") return { kicked: false, reason: "already_ready" };

    const opts = resolveLaunchOpts(overrides);
    if ("error" in opts) {
      clearRuntimeState({ status: "failed", error: opts.error, at: Date.now() });
      return { kicked: false, reason: opts.error };
    }

    const launchGen = ++launchGeneration;
    state = { status: "starting", startedAt: Date.now() };

    // Fire-and-forget: this promise resolves in the background while tool calls
    // return immediately. State is mutated in the closures below.
    void (async () => {
      try {
        const daemon = await launchDaemon(opts);
        if (launchGen !== launchGeneration) {
          try {
            await daemon.stop();
          } catch {
            /* best effort */
          }
          return;
        }
        daemonRef = daemon;
        toolset = buildServerToolset({
          adapter: daemon.adapter,
          sessionId: `mcp-${process.pid}-${Date.now()}`,
          daemonPid: daemon.pid,
        });
        state = { status: "ready", pid: daemon.pid, since: Date.now() };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (launchGen !== launchGeneration) {
          return;
        }
        state = { status: "failed", error: msg, at: Date.now() };
        daemonRef = null;
        toolset = null;
      }
    })();

    return { kicked: true };
  }

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS,
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const name = req.params.name;
    const args = (req.params.arguments ?? {}) as Record<string, unknown>;

    // ---- LIFECYCLE / HEALTH tools (always non-blocking) ----

    if (name === "xedit_status") {
      return jsonResult({ ok: true, tool: name, data: statusFields(state, daemonRef) });
    }

    if (name === "xedit_start") {
      // Extract override args (all optional). Unknown extra keys ignored.
      const overrides: LaunchOverrides = {
        launcherPath: typeof args.launcherPath === "string" ? args.launcherPath : undefined,
        gameMode: typeof args.gameMode === "string" ? args.gameMode : undefined,
        dataPath: typeof args.dataPath === "string" ? args.dataPath : undefined,
        pluginsFile: typeof args.pluginsFile === "string" ? args.pluginsFile : undefined,
        moProfile: typeof args.moProfile === "string" ? args.moProfile : undefined,
      };
      const kick = kickoffLaunch(overrides);
      const body = {
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        kicked: kick.kicked,
        message: kick.kicked
          ? "Daemon launch initiated in the background. Poll xedit_status until status='ready'."
          : kick.reason === "already_ready"
            ? "Daemon is already ready."
            : kick.reason === "already_starting"
              ? "Daemon launch already in progress. Poll xedit_status until status='ready'."
              : (kick.reason ?? "Launch could not be initiated."),
      };
      return jsonResult(body);
    }

    if (name === "xedit_health") {
      if (state.status !== "ready" || !daemonRef) {
        return jsonResult({
          ok: true,
          tool: name,
          data: { ...statusFields(state, daemonRef), responsive: false },
          hint: state.status === "not_started"
            ? "Daemon not started. Call xedit_start."
            : state.status === "starting"
              ? "Daemon still starting. Poll xedit_status."
              : "Daemon failed to start; inspect data.error.",
        });
      }
      try {
        const ping = await daemonRef.adapter.call({ command: "system.ping", args: {} });
        return jsonResult({
          ok: true,
          tool: name,
          data: {
            ...statusFields(state, daemonRef),
            responsive: ping.ok === true,
            pingEnvelope: ping,
          },
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return jsonResult({
          ok: true,
          tool: name,
          data: {
            ...statusFields(state, daemonRef),
            responsive: false,
            pingError: msg,
          },
          hint: "Daemon claimed ready but did not respond to system.ping. It may be a zombie; consider restarting MO2.",
        });
      }
    }

    if (name === "xedit_dirty") {
      const dirty = await getDirtyState();
      return jsonResult(dirty.body, !dirty.body.ok);
    }

    if (name === "xedit_stop") {
      const force = args.force === true;

      if (state.status === "not_started") {
        return jsonResult({
          ok: true,
          tool: name,
          data: statusFields(state, daemonRef),
          message: "Daemon already stopped.",
        });
      }

      if (state.status === "ready") {
        const dirty = await getDirtyState();
        if (dirty.ok) {
          const data = dirty.body.data as { dirty?: boolean; dirtyFiles?: string[]; unsavedChangeCount?: number };
          if (data.dirty && !force) {
            return jsonResult({
              ok: false,
              tool: name,
              code: "dirty_state",
              summary: "xEdit has unsaved changes. Refusing to stop without force=true.",
              data,
              hint: "Either save the dirty files first, or call xedit_stop({ force: true }) to abandon the in-memory edits.",
            }, true);
          }
        }
      }

      const current = daemonRef;
      clearRuntimeState();
      if (current) {
        try {
          await current.stop();
        } catch {
          /* best effort */
        }
      }
      return jsonResult({
        ok: true,
        tool: name,
        data: { status: "not_started" },
        message: "Daemon stopped and MCP runtime state cleared.",
      });
    }

    if (name === "xedit_restart") {
      const force = args.force === true;
      const overrides: LaunchOverrides = {
        launcherPath: typeof args.launcherPath === "string" ? args.launcherPath : undefined,
        gameMode: typeof args.gameMode === "string" ? args.gameMode : undefined,
        dataPath: typeof args.dataPath === "string" ? args.dataPath : undefined,
        pluginsFile: typeof args.pluginsFile === "string" ? args.pluginsFile : undefined,
        moProfile: typeof args.moProfile === "string" ? args.moProfile : undefined,
      };

      if (state.status === "ready") {
        const dirty = await getDirtyState();
        if (dirty.ok) {
          const data = dirty.body.data as { dirty?: boolean; dirtyFiles?: string[]; unsavedChangeCount?: number };
          if (data.dirty && !force) {
            return jsonResult({
              ok: false,
              tool: name,
              code: "dirty_state",
              summary: "xEdit has unsaved changes. Refusing to restart without force=true.",
              data,
              hint: "Either save the dirty files first, or call xedit_restart({ force: true, ... }) to abandon the in-memory edits and relaunch with the new overrides.",
            }, true);
          }
        }
      }

      const current = daemonRef;
      clearRuntimeState();
      if (current) {
        try {
          await current.stop();
        } catch {
          /* best effort */
        }
      }
      const kick = kickoffLaunch(overrides);
      return jsonResult({
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        kicked: kick.kicked,
        message: kick.kicked
          ? "Daemon restart initiated in the background. Poll xedit_status until status='ready'."
          : (kick.reason ?? "Restart could not be initiated."),
      });
    }

    // ---- DOMAIN tools ----

    if (name === "xedit_session") {
      if (state.status === "ready" && toolset) {
        try {
          const env = await toolset.invoke("xedit_session", args);
          return jsonResult(env, !env.ok);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return jsonResult({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }, true);
        }
      }
      // Not ready: auto-kick the launch if not yet started, then surface status.
      if (state.status === "not_started") {
        kickoffLaunch();
      }
      return jsonResult({
        ok: true,
        tool: name,
        data: statusFields(state, daemonRef),
        hint: state.status === "failed"
          ? "Launch failed; inspect data.error. Call xedit_start to retry."
          : "Daemon not ready yet; poll xedit_status until status='ready'.",
      });
    }

    // Other domain tools require ready
    if (state.status !== "ready" || !toolset) {
      return jsonResult({
        ok: false,
        tool: name,
        code: "not_ready",
        summary: `Daemon is not ready (status='${state.status}').`,
        data: statusFields(state, daemonRef),
        hint: state.status === "not_started"
          ? "Call xedit_start, then poll xedit_status until status='ready'."
          : state.status === "starting"
            ? "Launch in progress. Poll xedit_status."
            : "Launch failed; inspect data.error. Call xedit_start to retry.",
      }, true);
    }

    try {
      const env = await toolset.invoke(name, args);
      return jsonResult(env, !env.ok);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResult({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }, true);
    }
  });

  const shutdown = async (signal: string) => {
    process.stderr.write(`xedit-mcp received ${signal}, shutting down...\n`);
    if (daemonRef) {
      try { await daemonRef.stop(); } catch { /* best effort */ }
    }
    process.exit(0);
  };
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  await server.connect(new StdioServerTransport());
}

// Detect "invoked as the main entry" cross-platform. On Windows, naive string
// compare against `file://${argv[1]}` fails because of backslash + slash-count
// differences. Use pathToFileURL to normalize. (See earlier P5 bugfix commit.)
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
