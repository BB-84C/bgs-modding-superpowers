import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";

import { discoverPacks } from "./discovery/index.js";
import { refuse } from "./envelope/index.js";
import { KB_ERROR_CODES, type Envelope } from "./envelope/types.js";
import { openSessions } from "./session/index.js";
import { makeCheckUpdatesTool } from "./tools/check-updates.js";
import { makeGetTool } from "./tools/get.js";
import { makeInstallPackTool } from "./tools/install-pack.js";
import { makeQueryTool } from "./tools/query.js";
import { makeStatusTool } from "./tools/status.js";

const SERVER_NAME = "bgs-kb-mcp";
const SERVER_VERSION = "0.1.0";

export const TOOL_DEFINITIONS = [
  {
    name: "bgs_kb_status",
    description: "Returns loaded KB packs, cache roots, versions, and compatibility warnings. Works before MO2/xEdit are configured.",
  },
  {
    name: "bgs_kb_query",
    description: "Searches the local BGS Modding knowledge base (SQLite + FTS5 + BM25) across loaded packs. Supports game/domain/pack filters.",
  },
  {
    name: "bgs_kb_get",
    description: "Fetches one full KB record by id, optionally merged for a specific game variant.",
  },
  {
    name: "bgs_kb_check_updates",
    description: "Checks loaded KB packs against the latest GitHub Release manifest-index.json and reports available upgrades.",
  },
  {
    name: "bgs_kb_install_pack",
    description: "Downloads, verifies, and installs a pinned KB pack version into the local cache. Supports dryRun verification.",
  },
].map((tool) => ({ ...tool, inputSchema: { type: "object" as const, additionalProperties: true } }));

export type ToolHandler = (args: Record<string, unknown>) => Promise<Envelope>;

export interface ServerToolsetOptions {
  status: ToolHandler;
  query: ToolHandler;
  get: ToolHandler;
  checkUpdates: ToolHandler;
  installPack: ToolHandler;
}

export interface ServerToolset {
  list: () => typeof TOOL_DEFINITIONS;
  invoke: (name: string, args: Record<string, unknown>) => Promise<Envelope>;
}

export function jsonResult(body: unknown, isError = false) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(body) }],
    isError,
  };
}

export function buildServerToolset(opts: ServerToolsetOptions): ServerToolset {
  const handlers: Record<string, ToolHandler> = {
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
      } catch (error) {
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

export async function main(): Promise<void> {
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
    const envelope = await toolset.invoke(req.params.name, (req.params.arguments ?? {}) as Record<string, unknown>);
    return jsonResult(envelope, !envelope.ok);
  });

  const shutdown = (signal: string) => {
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
  if (!argv) return false;
  try {
    return import.meta.url === pathToFileURL(argv).href;
  } catch {
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
