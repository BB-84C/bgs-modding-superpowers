import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

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

// Production entry: stdio MCP server (Batch 1 stub — real wiring comes via buildServerToolset()).
export async function main(): Promise<void> {
  const server = new Server(
    { name: "xedit-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      { name: "xedit_session", description: "Ensure daemon, return session summary." },
      { name: "xedit_list_capabilities", description: "Curated digest + live drift report." },
      { name: "xedit_find_record", description: "Locate records by formId or editorId." },
      { name: "xedit_read_record", description: "Composite read (record + winning + base + conflict)." },
      { name: "xedit_inspect_conflicts", description: "Conflict audit verdict + winning + referencedBy." },
      { name: "xedit_call", description: "Atomic passthrough for any native daemon command (still in harness)." },
    ].map((t) => ({ ...t, inputSchema: { type: "object" } })),
  }));
  server.setRequestHandler(CallToolRequestSchema, async () => ({
    content: [{ type: "text", text: JSON.stringify({ ok: false, code: "not_wired", hint: "Production entry requires adapter wiring; use buildServerToolset()." }) }],
    isError: true,
  }));
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
