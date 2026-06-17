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
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
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
import type { ToolContext } from "./types.js";

async function main(): Promise<void> {
  const sessionId = randomUUID();
  const lifecycle = new Lifecycle();
  lifecycle.markStarting();
  const binding = new BindingManager();
  const runtimeRoot = join(tmpdir(), "mo2-mcp-runtime");
  const audit = new AuditLogger(join(runtimeRoot, "audit"), sessionId);
  const snapshots = new SnapshotManager(join(runtimeRoot, "snapshots"), sessionId);
  const plans = new PlanCache();
  const rules = getAllRules();

  const ctx: ToolContext = {
    binding,
    sessionId,
    plans,
    snapshots,
    audit,
  };

  const server = new Server(
    { name: "mo2-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

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
        ? (zodToJsonSchema(t.inputSchema, { target: "openApi3" }) as Record<string, unknown>)
        : (t.inputSchema as Record<string, unknown>);
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
    }) as any;
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
      process.stderr.write(
        `[mo2-mcp] eager bind ${snapshot.state} (${snapshot.mo2Root ?? eagerRoot})` +
          (snapshot.error ? `: ${snapshot.error.message}` : "") +
          "\n",
      );
    } catch (error) {
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
 * Ensure the inputSchema returned via tools/list is a clean top-level
 * `type: "object"` schema with NO top-level `anyOf` / `oneOf` / `allOf`.
 *
 * Background:
 *   - Zod `discriminatedUnion("mode", ...)` and `z.union([...])` convert to
 *     a top-level `{ anyOf: [...] }` (or `oneOf`/`allOf`) shape via
 *     zodToJsonSchema. That is valid JSON Schema but NOT a valid MCP
 *     `inputSchema` once we put it on the wire to Anthropic.
 *   - Anthropic's tool-use API explicitly rejects top-level
 *     `oneOf`/`allOf`/`anyOf` in `input_schema`, even when `type: "object"`
 *     is also declared. The error surface is:
 *         "tools.<N>.custom.input_schema: input_schema does not support
 *          oneOf, allOf, or anyOf at the top level"
 *     This crashes tool registration entirely on every Anthropic-backed
 *     OpenCode session (claude-opus-4-7 / claude-sonnet-4-* etc.). OpenAI's
 *     strict validator happens to accept the `{type:"object", ..., anyOf:[...]}`
 *     wrapped shape, which is why the bug looks "Anthropic-only" from the
 *     outside.
 *   - The sibling MCP `tools/xedit-mcp` solves this by hand-writing object
 *     schemas with all modes' properties merged at top level (see its
 *     `xedit_find_record` comment: "top-level oneOf/anyOf/allOf/enum/not is
 *     forbidden by OpenAI-style strict tool-schema backends"). The real
 *     branch-by-branch validation lives in the Zod `safeParse` inside
 *     `dispatch.ts`, NOT in the wire schema.
 *
 * What this function does:
 *   1. If `schema` is already `type: "object"` AND carries no top-level
 *      union keyword, pass it through unchanged.
 *   2. Otherwise collect all union variants from `anyOf` / `oneOf` / `allOf`.
 *   3. Hoist shared discriminant properties (a property that appears in
 *      every branch with `const` or single-value `enum`) into top-level
 *      `properties` with a unioned `enum`. Mark them `required` only if
 *      every branch requires them. This is the BUG-13 Lane A hoist that
 *      gives OpenAI tool-callers an anchor for argument decoding.
 *   4. ALSO merge each branch's other properties into top-level `properties`
 *      (first-wins). This gives LLMs visibility into the per-branch field
 *      shapes — they can see that `apply` mode wants `plan_id`, etc. —
 *      without leaking the union keyword onto the wire.
 *   5. Set `additionalProperties: true` so branch-specific fields not
 *      named here are still accepted by clients that enforce the wire
 *      schema strictly.
 *   6. DROP the original `anyOf` / `oneOf` / `allOf` keyword entirely.
 *
 * !!! DO NOT REINTRODUCE `[kw]: branches` AT THE TOP LEVEL !!!
 *   That was the v1.2-pre shape (BUG-13 Lane A pre-fix) and was the cause
 *   of the recurring Anthropic-side
 *     "input_schema does not support oneOf, allOf, or anyOf at the top level"
 *   crash. The real per-branch validator is Zod inside `dispatch.ts`; the
 *   wire schema must stay anyOf-free. If a future change needs the branch
 *   shape preserved for some external consumer, add a SEPARATE field
 *   (e.g. `x-branches`) outside the JSON Schema standard keyword set; do
 *   NOT use anyOf/oneOf/allOf at the top level.
 *   See also: D:\awesome-bgs-mod-master\AGENTS.md — "MCP inputSchema
 *   Anthropic Compatibility (2026-06-17)".
 */
export function normalizeMcpInputSchema(
  schema: Record<string, unknown>,
): Record<string, unknown> {
  const fallback: Record<string, unknown> = {
    type: "object",
    properties: {},
    additionalProperties: true,
  };
  if (!schema || typeof schema !== "object") return fallback;

  const unionKeywords = ["anyOf", "oneOf", "allOf"] as const;
  const hasUnion = unionKeywords.some((kw) => Array.isArray(schema[kw]));

  // Clean object schema with no union keyword: pass through.
  if (!hasUnion && schema.type === "object") {
    return schema;
  }

  // Collect branches across whichever union keyword(s) appear.
  const branches: unknown[] = [];
  for (const kw of unionKeywords) {
    const v = schema[kw];
    if (Array.isArray(v)) branches.push(...v);
  }

  // Discriminant hoist (preserves BUG-13 Lane A semantics for OpenAI).
  const { properties: discriminantProps, required: discriminantRequired } =
    extractDiscriminants(branches);

  // Merge all non-discriminant branch properties so LLMs see every field.
  const mergedProperties: Record<string, unknown> = { ...discriminantProps };
  const topProps = schema.properties;
  if (topProps && typeof topProps === "object") {
    for (const [k, val] of Object.entries(topProps as Record<string, unknown>)) {
      if (!(k in mergedProperties)) mergedProperties[k] = val;
    }
  }
  for (const branch of branches) {
    if (!branch || typeof branch !== "object") continue;
    const bp = (branch as Record<string, unknown>).properties;
    if (bp && typeof bp === "object") {
      for (const [k, val] of Object.entries(bp as Record<string, unknown>)) {
        if (!(k in mergedProperties)) mergedProperties[k] = val;
      }
    }
  }

  const result: Record<string, unknown> = {
    type: "object",
    properties: mergedProperties,
    additionalProperties: true,
  };
  if (discriminantRequired.length > 0) {
    result.required = discriminantRequired;
  }
  // NOTE: do NOT add `anyOf`/`oneOf`/`allOf` here. See the function-level
  // doc comment for why; Anthropic's tool-use API rejects the resulting
  // schema and the whole MCP fails to register.
  return result;
}

interface HoistedDiscriminants {
  properties: Record<string, unknown>;
  required: string[];
}

/**
 * Scan union branches for discriminant properties — those that appear in
 * EVERY branch and carry either `const` or a single-value `enum`. Hoist
 * each such property into the parent `properties` map with a unioned enum
 * across branches. A discriminant is included in top-level `required` only
 * if every branch requires it; otherwise the hoisted property is advisory.
 *
 * Returns empty properties + required when no shared discriminant is found
 * (preserves the prior permissive wrap shape).
 */
function extractDiscriminants(branches: unknown): HoistedDiscriminants {
  if (!Array.isArray(branches) || branches.length === 0) {
    return { properties: {}, required: [] };
  }

  type Candidate = { values: unknown[]; type: string | undefined };
  const perBranch: Array<Map<string, Candidate>> = [];
  const requiredPerBranch: Array<Set<string>> = [];

  for (const branch of branches) {
    if (!branch || typeof branch !== "object") {
      return { properties: {}, required: [] };
    }
    const b = branch as Record<string, unknown>;
    const props =
      b.properties && typeof b.properties === "object"
        ? (b.properties as Record<string, unknown>)
        : {};
    const req = Array.isArray(b.required) ? (b.required as string[]) : [];
    const map = new Map<string, Candidate>();
    for (const [propName, propSchema] of Object.entries(props)) {
      if (!propSchema || typeof propSchema !== "object") continue;
      const ps = propSchema as Record<string, unknown>;
      let values: unknown[] | undefined;
      if ("const" in ps) {
        values = [ps.const];
      } else if (Array.isArray(ps.enum) && ps.enum.length === 1) {
        values = [ps.enum[0]];
      }
      if (values === undefined) continue;
      map.set(propName, {
        values,
        type: typeof ps.type === "string" ? ps.type : undefined,
      });
    }
    perBranch.push(map);
    requiredPerBranch.push(new Set(req));
  }

  // Find props that appear in EVERY branch as a discriminant candidate.
  const firstBranch = perBranch[0];
  const commonPropNames: string[] = [];
  for (const propName of firstBranch.keys()) {
    if (perBranch.every((b) => b.has(propName))) {
      commonPropNames.push(propName);
    }
  }

  if (commonPropNames.length === 0) {
    return { properties: {}, required: [] };
  }

  const hoistedProperties: Record<string, unknown> = {};
  const hoistedRequired: string[] = [];
  for (const propName of commonPropNames) {
    const allValues: unknown[] = [];
    const types = new Set<string>();
    for (const b of perBranch) {
      const cand = b.get(propName)!;
      for (const v of cand.values) {
        if (!allValues.includes(v)) allValues.push(v);
      }
      if (cand.type !== undefined) types.add(cand.type);
    }
    const hoistedProp: Record<string, unknown> = {};
    if (types.size === 1) {
      hoistedProp.type = [...types][0];
    }
    hoistedProp.enum = allValues;
    hoistedProperties[propName] = hoistedProp;
    if (requiredPerBranch.every((r) => r.has(propName))) {
      hoistedRequired.push(propName);
    }
  }

  return { properties: hoistedProperties, required: hoistedRequired };
}
