import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { statSync } from "node:fs";
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
import { launchDaemon } from "./launch.js";
export function buildServerToolset(opts) {
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
    const handlers = {
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
function resolveLaunchOpts(overrides = {}) {
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
    }
    catch {
        return {
            error: "xedit-mcp is not configured. Set env vars on the MCP server: " +
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
    { name: "xedit_session", description: "Non-blocking. If the daemon is ready: returns gameMode, loadOrderSize, daemonPid. If not_started: auto-initiates launch. Otherwise: returns current status + hint to poll xedit_status." },
    { name: "xedit_list_capabilities", description: "Requires the daemon to be ready. Returns the curated 49-command digest + live drift report. Fast-fails with code='not_ready' otherwise." },
    { name: "xedit_find_record", description: "Requires the daemon to be ready. Locates records by {file, formId} or {editorId}. Fast-fails with code='not_ready' otherwise." },
    { name: "xedit_read_record", description: "Requires the daemon to be ready. Composite read: record + winning override + base record + conflict status. Fast-fails with code='not_ready' otherwise." },
    { name: "xedit_inspect_conflicts", description: "Requires the daemon to be ready. Conflict audit verdict + winning + referencedBy. Fast-fails with code='not_ready' otherwise." },
    { name: "xedit_call", description: "Requires the daemon to be ready. Atomic passthrough for any native daemon command, still in-harness. Fast-fails with code='not_ready' otherwise." },
].map((t) => ({ ...t, inputSchema: { type: "object", additionalProperties: true } }));
// Helper to build the MCP CallTool response. Return type is loose so the
// SDK's expected ServerResult shape is satisfied without import-coupling.
function jsonResult(body, isError = false) {
    return {
        content: [{ type: "text", text: JSON.stringify(body) }],
        isError,
    };
}
function statusFields(state, daemon) {
    const out = { status: state.status };
    if (state.status === "starting") {
        out.startedAt = state.startedAt;
        out.elapsedSeconds = Math.round((Date.now() - state.startedAt) / 1000);
    }
    else if (state.status === "ready") {
        out.pid = state.pid;
        out.readySince = state.since;
        if (daemon)
            out.daemonPid = daemon.pid;
    }
    else if (state.status === "failed") {
        out.error = state.error;
        out.failedAt = state.at;
    }
    return out;
}
export async function main() {
    const server = new Server({ name: "xedit-mcp", version: "0.1.0" }, { capabilities: { tools: {} } });
    let state = { status: "not_started" };
    let toolset = null;
    let daemonRef = null;
    function kickoffLaunch(overrides = {}) {
        if (state.status === "starting")
            return { kicked: false, reason: "already_starting" };
        if (state.status === "ready")
            return { kicked: false, reason: "already_ready" };
        const opts = resolveLaunchOpts(overrides);
        if ("error" in opts) {
            state = { status: "failed", error: opts.error, at: Date.now() };
            return { kicked: false, reason: opts.error };
        }
        state = { status: "starting", startedAt: Date.now() };
        // Fire-and-forget: this promise resolves in the background while tool calls
        // return immediately. State is mutated in the closures below.
        void (async () => {
            try {
                const daemon = await launchDaemon(opts);
                daemonRef = daemon;
                toolset = buildServerToolset({
                    adapter: daemon.adapter,
                    sessionId: `mcp-${process.pid}-${Date.now()}`,
                    daemonPid: daemon.pid,
                });
                state = { status: "ready", pid: daemon.pid, since: Date.now() };
            }
            catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
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
        const args = (req.params.arguments ?? {});
        // ---- LIFECYCLE / HEALTH tools (always non-blocking) ----
        if (name === "xedit_status") {
            return jsonResult({ ok: true, tool: name, data: statusFields(state, daemonRef) });
        }
        if (name === "xedit_start") {
            // Extract override args (all optional). Unknown extra keys ignored.
            const overrides = {
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
            }
            catch (err) {
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
        // ---- DOMAIN tools ----
        if (name === "xedit_session") {
            if (state.status === "ready" && toolset) {
                try {
                    const env = await toolset.invoke("xedit_session", args);
                    return jsonResult(env, !env.ok);
                }
                catch (err) {
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
        }
        catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            return jsonResult({ ok: false, tool: name, code: "internal_error", summary: msg, hint: msg }, true);
        }
    });
    const shutdown = async (signal) => {
        process.stderr.write(`xedit-mcp received ${signal}, shutting down...\n`);
        if (daemonRef) {
            try {
                await daemonRef.stop();
            }
            catch { /* best effort */ }
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
    if (!argv)
        return false;
    try {
        return import.meta.url === pathToFileURL(argv).href;
    }
    catch {
        return false;
    }
})();
if (invokedAsMain) {
    main().catch((e) => {
        console.error(e);
        process.exit(1);
    });
}
//# sourceMappingURL=index.js.map