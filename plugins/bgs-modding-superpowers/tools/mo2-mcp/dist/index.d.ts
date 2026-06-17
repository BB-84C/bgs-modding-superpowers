import "./pipeline/rules/STOCK001-stock-game-deny.js";
import "./pipeline/rules/PATHSAFE001-path-traversal-deny.js";
import "./pipeline/rules/NAMESAFE001-no-path-in-name.js";
import "./pipeline/rules/CEILING001-permission-ceiling.js";
import "./tools/mo2-session.js";
import "./tools/mo2-status.js";
import "./tools/mo2-machine-contract.js";
import "./tools/mo2-modlist.js";
import "./tools/mo2-pluginlist.js";
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
 * Ensure the inputSchema returned via tools/list always has type==="object"
 * at the top level. Zod discriminated unions produce {anyOf:[...]} (or
 * {oneOf}/{allOf}) -- valid JSON Schema, but MCP's tool-call wire format
 * needs an object container so the args object can be schema-validated.
 *
 * If the top-level shape already has type==="object", pass it through. Else
 * wrap it as { type:"object", <keyword>:..., properties:..., additionalProperties:true }.
 *
 * BUG-13 (Lane A): when the union has a shared discriminant property (a
 * property that exists in every branch and is a const/single-value-enum
 * literal), hoist it into top-level `properties` with a unioned `enum` so
 * OpenAI tool-callers have an anchor for argument decoding. The original
 * anyOf/oneOf/allOf is preserved at top level so branch-by-branch validators
 * still see the full per-mode shape. Branch-specific fields stay permissive
 * via `additionalProperties: true`.
 *
 * Backward-compatible: claude-opus-4-7 already handled the empty-properties
 * shape correctly (17/17 in phase4final-beta); the hoist is additive and
 * keeps that working.
 */
export declare function normalizeMcpInputSchema(schema: Record<string, unknown>): Record<string, unknown>;
