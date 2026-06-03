import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { discoverPacks } from "./discovery/index.js";
import { refuse } from "./envelope/index.js";
import { KB_ERROR_CODES } from "./envelope/types.js";
import { openSessions } from "./session/index.js";
import { makeCheckUpdatesTool } from "./tools/check-updates.js";
import { makeGetTool } from "./tools/get.js";
import { makeInstallPackTool } from "./tools/install-pack.js";
import { makeQueryTool } from "./tools/query.js";
import { makeStatusTool } from "./tools/status.js";
import { DOMAIN_VALUES, GAME_CODE_VALUES } from "./types/enums.js";
const SERVER_NAME = "bgs-kb-mcp";
const SERVER_VERSION = "0.1.0";
const RECORD_KIND_VALUES = ["rule", "workflow", "gotcha", "explanation", "source-map"];
const DETAIL_LEVEL_VALUES = ["summary", "expanded"];
// Explicit per-tool JSON Schemas. These mirror the Zod `.strict()` contracts in
// each tool handler so MCP clients (OpenCode, Claude Code, Codex) can route the
// model's arguments correctly. The previous loose `additionalProperties: true`
// shortcut left OpenCode unable to forward arguments to the parameterized
// tools, which surfaced as 'Invalid bgs_kb_query request: query is required'.
export const TOOL_DEFINITIONS = [
    {
        name: "bgs_kb_status",
        description: "Returns loaded KB packs, cache roots, versions, and compatibility warnings. Works before MO2/xEdit are configured.",
        inputSchema: {
            type: "object",
            properties: {},
            additionalProperties: false,
        },
    },
    {
        name: "bgs_kb_query",
        description: "Searches the local BGS Modding knowledge base (SQLite + FTS5 + BM25) across loaded packs. Supports game/domain/pack filters. Pass { query, games?, domains?, toolchains?, kinds?, packIds?, maxResults?, detailLevel?, includeVariants?, includeSources?, cursor? }.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Free-text FTS query against title, body, and canonical answer." },
                games: { type: "array", items: { type: "string", enum: [...GAME_CODE_VALUES] }, description: "Filter hits to records that apply to any of these game codes." },
                domains: { type: "array", items: { type: "string", enum: [...DOMAIN_VALUES] }, description: "Filter hits to records that target any of these knowledge domains." },
                toolchains: { type: "array", items: { type: "string" }, description: "Filter hits to records that mention any of these toolchains (e.g. 'xedit', 'mutagen')." },
                kinds: { type: "array", items: { type: "string", enum: [...RECORD_KIND_VALUES] }, description: "Filter hits by KB record kind." },
                packIds: { type: "array", items: { type: "string" }, description: "Restrict the search to specific pack ids." },
                maxResults: { type: "integer", minimum: 1, description: "Cap on returned hits; capped server-side at 20." },
                detailLevel: { type: "string", enum: [...DETAIL_LEVEL_VALUES], description: "summary = title + snippet only; expanded = include bodyExcerpt." },
                includeVariants: { type: "boolean", description: "Include per-game variantNotes in each hit. Default: true." },
                includeSources: { type: "boolean", description: "Include the sources array in each hit. Default: true." },
                cursor: { type: "string", description: "Reserved for future paging. Currently ignored." },
            },
            required: ["query"],
            additionalProperties: false,
        },
    },
    {
        name: "bgs_kb_get",
        description: "Fetches one full KB record by id, optionally merged for a specific game variant. Pass { id, game?, packId? }.",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "string", minLength: 1, description: "Canonical record id, e.g. 'load-order.fallout4.plugins-txt.v1'." },
                game: { type: "string", enum: [...GAME_CODE_VALUES], description: "Optional game code; when set, variant additions/warnings for that game are merged into the returned record." },
                packId: { type: "string", minLength: 1, description: "Optional pack id to disambiguate when multiple packs declare the same record id." },
            },
            required: ["id"],
            additionalProperties: false,
        },
    },
    {
        name: "bgs_kb_check_updates",
        description: "Checks loaded KB packs against the latest GitHub Release manifest-index.json and reports available upgrades.",
        inputSchema: {
            type: "object",
            properties: {},
            additionalProperties: false,
        },
    },
    {
        name: "bgs_kb_install_pack",
        description: "Downloads, verifies, and installs a pinned KB pack version into the local cache. Supports dryRun verification. Pass { packId, version, dryRun? }.",
        inputSchema: {
            type: "object",
            properties: {
                packId: { type: "string", minLength: 1, description: "Canonical pack id, e.g. 'bgs-kb-core'." },
                version: { type: "string", minLength: 1, description: "Exact pack version; the string 'latest' is rejected — run bgs_kb_check_updates first." },
                dryRun: { type: "boolean", description: "If true, downloads and verifies the archive without writing the final install path." },
            },
            required: ["packId", "version"],
            additionalProperties: false,
        },
    },
];
export function jsonResult(body, isError = false) {
    return {
        content: [{ type: "text", text: JSON.stringify(body) }],
        isError,
    };
}
export function buildServerToolset(opts) {
    const handlers = {
        bgs_kb_status: opts.status,
        bgs_kb_query: opts.query,
        bgs_kb_get: opts.get,
        bgs_kb_check_updates: opts.checkUpdates,
        bgs_kb_install_pack: opts.installPack,
    };
    return {
        list: () => TOOL_DEFINITIONS,
        invoke: async (name, args) => {
            const handler = handlers[name];
            if (!handler) {
                return refuse({
                    tool: name,
                    summary: `Unknown tool: ${name}`,
                    code: KB_ERROR_CODES.INVALID_REQUEST,
                    hint: "List available tools via tools/list and call one of: bgs_kb_status, bgs_kb_query, bgs_kb_get, bgs_kb_check_updates, bgs_kb_install_pack.",
                    severity: "MEDIUM",
                });
            }
            try {
                return await handler(args);
            }
            catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                return refuse({
                    tool: name,
                    summary: `Internal error while running ${name}: ${message}`,
                    code: KB_ERROR_CODES.INTERNAL_ERROR,
                    hint: message,
                    detail: { message },
                    severity: "HIGH",
                });
            }
        },
    };
}
export async function main() {
    const discovery = await discoverPacks();
    const registry = openSessions(discovery.packs);
    const cachePackRoot = discovery.rootsScanned.find((root) => root.root === "cache")?.rootPath;
    const installCacheRoot = cachePackRoot ? dirname(cachePackRoot) : undefined;
    const toolset = buildServerToolset({
        status: makeStatusTool({ discovery, registry }),
        query: makeQueryTool({ registry }),
        get: makeGetTool({ registry }),
        checkUpdates: makeCheckUpdatesTool({ registry, currentPluginVersion: discovery.currentPluginVersion }),
        installPack: makeInstallPackTool({
            registry,
            cacheRoot: installCacheRoot ?? "",
            currentPluginVersion: discovery.currentPluginVersion,
            supportedSchemaVersion: discovery.supportedSchemaVersion,
        }),
    });
    const server = new Server({ name: SERVER_NAME, version: SERVER_VERSION }, { capabilities: { tools: {} } });
    server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: toolset.list() }));
    server.setRequestHandler(CallToolRequestSchema, async (req) => {
        const envelope = await toolset.invoke(req.params.name, (req.params.arguments ?? {}));
        return jsonResult(envelope, !envelope.ok);
    });
    const shutdown = (signal) => {
        process.stderr.write(`${SERVER_NAME} received ${signal}, shutting down...\n`);
        registry.closeAll();
        process.exit(0);
    };
    process.on("SIGINT", () => shutdown("SIGINT"));
    process.on("SIGTERM", () => shutdown("SIGTERM"));
    await server.connect(new StdioServerTransport());
}
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
    main().catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`${SERVER_NAME} startup failed: ${message}\n`);
        process.exit(1);
    });
}
//# sourceMappingURL=index.js.map