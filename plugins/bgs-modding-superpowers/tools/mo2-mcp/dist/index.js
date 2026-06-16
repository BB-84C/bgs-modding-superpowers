/**
 * MO2 MCP server bootstrap.
 *
 * Sequence:
 *   1. Build an unbound BindingManager (lazy MO2 root/session selection)
 *   2. Wire ToolContext with binding + plans + snapshots + audit (P-F9)
 *   3. Start MCP stdio server, register tools/list + tools/call handlers
 *   4. Best-effort eager auto-bind if BGS_MO2_ROOT is present
 *
 * Tools register via side-effect imports (S3+ adds them); S2 registers ZERO
 * tools — server boots clean and tools/list returns [].
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, } from "@modelcontextprotocol/sdk/types.js";
import { zodToJsonSchema } from "zod-to-json-schema";
import { ZodType } from "zod";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Lifecycle } from "./lifecycle.js";
import { BindingManager } from "./binding.js";
import { AuditLogger } from "./audit.js";
import { SnapshotManager } from "./snapshot.js";
import { PlanCache } from "./plan-apply.js";
import { getAllTools } from "./tool-registry.js";
import { getAllRules } from "./pipeline/registry.js";
import { dispatchToolCall } from "./dispatch.js";
import "./pipeline/rules/STOCK001-stock-game-deny.js"; // side-effect: register STOCK001
import "./pipeline/rules/PATHSAFE001-path-traversal-deny.js"; // side-effect: register PATHSAFE001
import "./pipeline/rules/NAMESAFE001-no-path-in-name.js"; // side-effect: register NAMESAFE001
import "./pipeline/rules/CEILING001-permission-ceiling.js"; // side-effect: register CEILING001
import "./tools/mo2-session.js"; // side-effect: register mo2_session
import "./tools/mo2-status.js"; // side-effect: register mo2_status
import "./tools/mo2-machine-contract.js"; // side-effect: register mo2_machine_contract
import "./tools/mo2-modlist.js"; // side-effect: register mo2_modlist
import "./tools/mo2-pluginlist.js"; // side-effect: register mo2_pluginlist
import "./tools/mo2-mod-info.js"; // side-effect: register mo2_mod_info
import "./tools/mo2-profile-ini-get.js"; // side-effect: register mo2_profile_ini_get
import "./tools/mo2-assets-summary.js"; // side-effect: register mo2_assets_summary
import "./tools/mo2-assets-conflicts.js"; // side-effect: register mo2_assets_conflicts
import "./tools/mo2-assets-resolve.js"; // side-effect: register mo2_assets_resolve
import "./tools/mo2-search-files.js"; // side-effect: register mo2_search_files
import "./tools/mo2-list-executables.js"; // side-effect: register mo2_list_executables
import "./tools/mo2-audit-query.js"; // side-effect: register mo2_audit_query
import "./tools/mo2-set-mod-notes.js"; // side-effect: register mo2_set_mod_notes
import "./tools/mo2-edit-meta.js"; // side-effect: register mo2_edit_meta
import "./tools/mo2-profile-ini-set.js"; // side-effect: register mo2_profile_ini_set
import "./tools/mo2-backup-mod.js"; // side-effect: register mo2_backup_mod
import "./tools/mo2-backup-profile.js"; // side-effect: register mo2_backup_profile
import "./tools/mo2-toggle-mod.js"; // side-effect: register mo2_toggle_mod
import "./tools/mo2-toggle-plugin.js"; // side-effect: register mo2_toggle_plugin
import "./tools/mo2-send-mod-to.js"; // side-effect: register mo2_send_mod_to
import "./tools/mo2-rollback.js"; // side-effect: register mo2_rollback
import "./tools/mo2-restore-profile.js"; // side-effect: register mo2_restore_profile
import "./tools/mo2-install.js"; // side-effect: register mo2_install
import "./tools/mo2-run-tool.js"; // side-effect: register mo2_run_tool
import "./tools/mo2-switch-profile.js"; // side-effect: register mo2_switch_profile
import "./tools/mo2-configure-executable.js"; // side-effect: register mo2_configure_executable
import "./tools/mo2-create-mod.js"; // side-effect: register mo2_create_mod
import "./tools/mo2-create-separator.js"; // side-effect: register mo2_create_separator
import "./tools/mo2-rename-mod.js"; // side-effect: register mo2_rename_mod
import "./tools/mo2-reinstall-mod.js"; // side-effect: register mo2_reinstall_mod
import "./tools/mo2-remove-mod.js"; // side-effect: register mo2_remove_mod
import "./tools/mo2-set-file-hidden.js"; // side-effect: register mo2_set_file_hidden
import "./tools/mo2-create-profile.js"; // side-effect: register mo2_create_profile
import "./tools/mo2-clone-profile.js"; // side-effect: register mo2_clone_profile
import "./tools/mo2-rename-profile.js"; // side-effect: register mo2_rename_profile
async function main() {
    const sessionId = randomUUID();
    const lifecycle = new Lifecycle();
    lifecycle.markStarting();
    const binding = new BindingManager();
    const runtimeRoot = join(tmpdir(), "mo2-mcp-runtime");
    const audit = new AuditLogger(join(runtimeRoot, "audit"), sessionId);
    const snapshots = new SnapshotManager(join(runtimeRoot, "snapshots"), sessionId);
    const plans = new PlanCache();
    const rules = getAllRules();
    const ctx = {
        binding,
        sessionId,
        plans,
        snapshots,
        audit,
    };
    const server = new Server({ name: "mo2-mcp", version: "0.1.0" }, { capabilities: { tools: {} } });
    // tools/list returns JSON Schema, not Zod schema. The registered tools
    // carry Zod schemas (which dispatch.ts uses for safeParse on every tool
    // call), so convert here. MCP requires the top-level inputSchema to be a
    // JSON Schema object with type==="object" -- but Zod discriminated unions
    // convert to top-level {anyOf:[...]} or {oneOf:[...]}, which strict
    // clients (OpenCode) reject as "Failed to get tools". Wrap any non-object
    // top-level shape in {type:"object", ...wrapped_keyword} so the result
    // always satisfies the MCP contract while preserving the union semantics
    // for clients that do unwrap them.
    server.setRequestHandler(ListToolsRequestSchema, async () => ({
        tools: getAllTools().map((t) => {
            const rawSchema = t.inputSchema instanceof ZodType
                ? zodToJsonSchema(t.inputSchema, { target: "openApi3" })
                : t.inputSchema;
            const inputSchema = normalizeMcpInputSchema(rawSchema);
            return {
                name: t.name,
                description: t.description,
                inputSchema,
            };
        }),
    }));
    server.setRequestHandler(CallToolRequestSchema, async (req) => {
        return dispatchToolCall({
            toolName: req.params.name,
            rawArgs: req.params.arguments,
            ctx,
            rules,
        });
    });
    lifecycle.markReady({
        sidecarPid: undefined,
        brokerPipeName: binding.getSnapshot().pipeConnected ? "connected" : undefined,
    });
    const transport = new StdioServerTransport();
    await server.connect(transport);
    // Eager auto-bind: if BGS_MO2_ROOT is set, do the bind BEFORE writing the
    // "ready" log so clients can treat the ready signal as "tools are usable
    // immediately". We await + try/catch so a failed bind never blocks server
    // startup — the server still becomes ready in unbound/failed state and the
    // agent can recover via mo2_session({ mo2Root, ... }).
    // BGS_MO2_PROFILE is also honored so the eager bind targets the right
    // profile when an install has multiple profiles (e.g. BB84自用 vs Default).
    if (process.env.BGS_MO2_ROOT) {
        const eagerRoot = process.env.BGS_MO2_ROOT;
        const eagerProfile = process.env.BGS_MO2_PROFILE;
        try {
            const snapshot = await binding.bind({ mo2Root: eagerRoot, profile: eagerProfile });
            process.stderr.write(`[mo2-mcp] eager bind ${snapshot.state} (${snapshot.mo2Root ?? eagerRoot})` +
                (snapshot.error ? `: ${snapshot.error.message}` : "") +
                "\n");
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            process.stderr.write(`[mo2-mcp] eager bind failed (${eagerRoot}): ${message}\n`);
        }
    }
    process.stderr.write(`mo2-mcp ready (session ${sessionId}, binding=${binding.getSnapshot().state})\n`);
}
main().catch((e) => {
    process.stderr.write(`mo2-mcp fatal: ${e}\n`);
    process.exit(1);
});
/**
 * Ensure the inputSchema returned via tools/list always has type==="object"
 * at the top level. Zod discriminated unions produce {anyOf:[...]} (or
 * {oneOf}/{allOf}) -- valid JSON Schema, but MCP's tool-call wire format
 * needs an object container so the args object can be schema-validated.
 *
 * If the top-level shape already has type==="object", pass it through. Else
 * wrap it as { type:"object", <keyword>:..., properties:{}, additionalProperties:true }
 * so the schema still describes the union for clients that look inside.
 */
function normalizeMcpInputSchema(schema) {
    if (schema && typeof schema === "object" && schema.type === "object")
        return schema;
    for (const kw of ["anyOf", "oneOf", "allOf"]) {
        if (kw in schema) {
            return {
                type: "object",
                properties: {},
                additionalProperties: true,
                [kw]: schema[kw],
            };
        }
    }
    // Fall through: anything we don't recognize, wrap permissively.
    return {
        type: "object",
        properties: {},
        additionalProperties: true,
    };
}
