import { z } from "zod";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { emitAudit } from "../audit-line.js";
// r6 supports.applyFilterExtensions (contract 0.14; 0.20 added regex + multiPattern
// sub-blocks). This tool wraps records.apply_filter with the new filter args so
// the agent can express "all REFRs inside CELL X whose EditorID matches
// ^(Iron|Steel)" as one typed call instead of constructing the JSON by hand
// through xedit_call.
// Each *Regex / *Pattern field accepts either a single string or an array of
// strings (multi-pattern OR semantics, contract 0.20). The Zod schema accepts
// both; the JSON Schema declares `type: "string"` for ergonomic single-pattern
// calls and the description tells the agent how to use multi-pattern.
const RegexOrArray = z.union([z.string().min(1), z.array(z.string().min(1)).min(1)]).optional();
const Args = z
    .object({
    file: z.string().min(1).optional(),
    parentFormId: z
        .string()
        .regex(/^(0x)?[0-9a-fA-F]{1,8}$/)
        .optional(),
    signatures: z.array(z.string().min(1)).min(1).optional(),
    editorIdRegex: RegexOrArray,
    displayNameRegex: RegexOrArray,
    fullNameRegex: RegexOrArray,
    baseEditorIdRegex: RegexOrArray,
    baseDisplayNameRegex: RegexOrArray,
    editorIdPattern: RegexOrArray,
    displayNamePattern: RegexOrArray,
    limit: z.number().int().positive().max(10000).optional(),
    offset: z.number().int().nonnegative().optional(),
})
    .refine((data) => {
    // At least one filter predicate must be supplied. "limit" / "offset" /
    // "file" alone do not constitute a filter — the agent must scope by at
    // least one of: parentFormId, signatures, or any *Regex / *Pattern.
    return Boolean(data.parentFormId ||
        data.signatures ||
        data.editorIdRegex ||
        data.displayNameRegex ||
        data.fullNameRegex ||
        data.baseEditorIdRegex ||
        data.baseDisplayNameRegex ||
        data.editorIdPattern ||
        data.displayNamePattern);
}, {
    message: "At least one filter predicate is required: parentFormId, signatures, or any *Regex / *Pattern field.",
})
    .refine((data) => !(data.editorIdPattern && data.editorIdRegex), { message: "editorIdPattern and editorIdRegex are mutually exclusive — pick one." })
    .refine((data) => !(data.displayNamePattern && data.displayNameRegex), { message: "displayNamePattern and displayNameRegex are mutually exclusive — pick one." });
/** Strip "0x" prefix from `parentFormId` for daemon forwarding. */
function stripParentFormIdPrefix(args) {
    if (typeof args.parentFormId !== "string")
        return args;
    const f = args.parentFormId;
    return f.startsWith("0x") || f.startsWith("0X")
        ? { ...args, parentFormId: f.slice(2) }
        : args;
}
/**
 * Daemon `records.apply_filter` requires `files: string[]` (array of plugin names),
 * NOT `file: string`. Our intent-tool schema accepts a singular `file` for ergonomic
 * single-plugin calls; translate it here before forwarding. Empirically verified
 * 2026-06-18 against daemon contract 0.20: omitting `files` triggers
 * `invalid_request: 'files' must contain at least one plugin name` even when the
 * caller meant "all loaded files" — the daemon does NOT default-include all files.
 *
 * Translation rules:
 *   - If caller passed `file: "X"`, send `files: ["X"]` and drop `file`.
 *   - If caller omitted `file`, leave `files` absent. Daemon will reject; caller
 *     must specify at least one plugin scope. (We surface that error directly.)
 *   - Pass-through `files` array if the caller already provided it (future-proof).
 */
function wrapFileAsFiles(args) {
    if (Array.isArray(args.files) && args.files.length > 0)
        return args;
    if (typeof args.file === "string" && args.file.length > 0) {
        const out = { ...args, files: [args.file] };
        delete out.file;
        return out;
    }
    return args;
}
export function makeFindRecordsByPatternHandler(opts) {
    return async (args) => {
        const ctx = opts.getContext();
        if (!ctx) {
            return refuse({
                tool: "xedit_find_records_by_pattern",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
        }
        const v = validateArgs(Args, args, { tool: "xedit_find_records_by_pattern" });
        if (v) {
            await emitAudit({ audit: opts.audit, tool: "xedit_find_records_by_pattern", args, env: v, ctx });
            return v;
        }
        const p = precheck({ tool: "xedit_find_records_by_pattern", args }, { ctx, needs: { daemon: true } });
        if (p) {
            await emitAudit({ audit: opts.audit, tool: "xedit_find_records_by_pattern", args, env: p, ctx });
            return p;
        }
        const r = await runRules({
            tool: "xedit_find_records_by_pattern",
            args,
            ctx,
            registry: opts.registry,
        });
        if (r.refusal) {
            await emitAudit({
                audit: opts.audit,
                tool: "xedit_find_records_by_pattern",
                args,
                env: r.refusal,
                ctx,
                ruleHits: r.ruleHits,
            });
            return r.refusal;
        }
        const daemonArgs = wrapFileAsFiles(stripParentFormIdPrefix(args));
        const native = await opts.adapter.call({
            command: "records.apply_filter",
            args: daemonArgs,
        });
        if (!native.ok) {
            const env = refuse({
                tool: "xedit_find_records_by_pattern",
                summary: `records.apply_filter failed: ${native.error.code}`,
                code: MCP_ERROR_CODES.DAEMON_ERROR,
                hint: native.error.message,
                detail: { daemonCode: native.error.code, daemonDetails: native.error.details },
            });
            await emitAudit({ audit: opts.audit, tool: "xedit_find_records_by_pattern", args, env, ctx });
            return env;
        }
        // Real daemon response shape (r6, contract 0.20):
        //   { matches: [{file, formId, signature, editorId?, displayName?}, ...],
        //     matchCount, truncated?, regexSlotsExhausted? }
        // Older shape used `hits`. Accept both.
        const result = (native.result ?? {});
        const rawMatches = Array.isArray(result.matches)
            ? result.matches
            : Array.isArray(result.hits)
                ? result.hits
                : [];
        const matches = rawMatches.map(normalizeMatch);
        const env = okEnv({
            tool: "xedit_find_records_by_pattern",
            summary: `apply_filter returned ${matches.length} match${matches.length === 1 ? "" : "es"}`,
            status: "completed",
            data: {
                matches,
                matchCount: typeof result.matchCount === "number" ? result.matchCount : matches.length,
                truncated: result.truncated === true,
                regexSlotsExhausted: result.regexSlotsExhausted === true,
            },
            warnings: r.warnings,
        });
        await emitAudit({
            audit: opts.audit,
            tool: "xedit_find_records_by_pattern",
            args,
            env,
            ctx,
            ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
        });
        return env;
    };
}
/**
 * Normalize one match entry. The daemon may wrap entries as
 * `{ locator: {file, formId, path}, object: {signature, editorId, displayName} }`
 * (mirroring records.find_by_editor_id) or return a flat record. Unwrap so the
 * caller always sees a flat `{file, formId, signature?, editorId?, displayName?}`.
 */
function normalizeMatch(entry) {
    if (entry === null || typeof entry !== "object")
        return {};
    const e = entry;
    const locator = e.locator && typeof e.locator === "object" ? e.locator : null;
    const object = e.object && typeof e.object === "object" ? e.object : null;
    if (!locator && !object)
        return e;
    return { ...(object ?? {}), ...(locator ?? {}) };
}
//# sourceMappingURL=find-records-by-pattern.js.map