import "./pipeline/rules/STOCK001-stock-game-deny.js";
import "./pipeline/rules/PATHSAFE001-path-traversal-deny.js";
import "./pipeline/rules/NAMESAFE001-no-path-in-name.js";
import "./pipeline/rules/CEILING001-permission-ceiling.js";
import "./tools/mo2-session.js";
import "./tools/mo2-status.js";
import "./tools/mo2-machine-contract.js";
import "./tools/mo2-modlist.js";
import "./tools/mo2-pluginlist.js";
import "./tools/mo2-plugin-warnings.js";
import "./tools/mo2-mod-info.js";
import "./tools/mo2-profile-ini-get.js";
import "./tools/mo2-assets-summary.js";
import "./tools/mo2-assets-conflicts.js";
import "./tools/mo2-assets-resolve.js";
import "./tools/mo2-search-files.js";
import "./tools/mo2-list-executables.js";
import "./tools/mo2-audit-query.js";
import "./tools/mo2-set-mod-notes.js";
import "./tools/mo2-edit-meta.js";
import "./tools/mo2-profile-ini-set.js";
import "./tools/mo2-backup-mod.js";
import "./tools/mo2-backup-profile.js";
import "./tools/mo2-toggle-mod.js";
import "./tools/mo2-toggle-plugin.js";
import "./tools/mo2-send-mod-to.js";
import "./tools/mo2-send-plugin-to.js";
import "./tools/mo2-rollback.js";
import "./tools/mo2-restore-profile.js";
import "./tools/mo2-install.js";
import "./tools/mo2-run-tool.js";
import "./tools/mo2-switch-profile.js";
import "./tools/mo2-configure-executable.js";
import "./tools/mo2-create-mod.js";
import "./tools/mo2-create-separator.js";
import "./tools/mo2-rename-mod.js";
import "./tools/mo2-reinstall-mod.js";
import "./tools/mo2-remove-mod.js";
import "./tools/mo2-set-file-hidden.js";
import "./tools/mo2-create-profile.js";
import "./tools/mo2-clone-profile.js";
import "./tools/mo2-rename-profile.js";
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
export declare function normalizeMcpInputSchema(schema: Record<string, unknown>): Record<string, unknown>;
