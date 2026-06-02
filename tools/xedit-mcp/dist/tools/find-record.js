import { z } from "zod";
import { runTool } from "../pipeline/compose.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
const ByFormId = z.object({
    file: z.string().min(1),
    // Accept both "0x0000003C" and bare "0000003C" — the daemon wants no 0x prefix; we
    // strip it before forwarding so agents can use either style.
    formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});
/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args) {
    if (typeof args.formId !== "string")
        return args;
    const f = args.formId;
    return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}
const ByEditorId = z.object({
    editorId: z.string().min(1),
    signature: z.string().optional(),
});
export const findRecordSpec = {
    name: "xedit_find_record",
    schema: z.union([ByFormId, ByEditorId]),
    needs: { daemon: true },
    command: "records.find_by_form_id",
    summary: (a) => a.formId ? `find ${String(a.formId)} in ${String(a.file)}` : `find editor ${String(a.editorId)}`,
};
export function makeFindRecordHandler(opts) {
    return async (args) => {
        const ctx = opts.getContext();
        if (!ctx) {
            return refuse({
                tool: "xedit_find_record",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
        }
        if (typeof args.formId === "string" && typeof args.file === "string") {
            const daemonArgs = stripFormIdPrefix(args);
            // Load-order check is owned by LOAD001 (rule layer) for uniform behavior
            // across all record-side tools; pipeline runs rules against the ORIGINAL
            // caller args (line 81 below passes `args`, not `daemonArgs`), so
            // LOAD001 still sees `file` as the caller passed it.
            return runTool({
                ...findRecordSpec,
                command: "records.find_by_form_id",
                needs: { daemon: true },
                shape: (result) => ({ locators: [normalizeLocator(result, args)] }),
            }, { args: daemonArgs, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit });
        }
        if (typeof args.editorId === "string") {
            return runTool({
                ...findRecordSpec,
                command: "records.find_by_editor_id",
                shape: (result) => {
                    const matches = result.matches ?? [];
                    return { locators: matches.map((m) => normalizeLocator(m, args)) };
                },
            }, { args, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit });
        }
        return refuse({
            tool: "xedit_find_record",
            summary: "Provide either {file, formId} or {editorId}",
            code: MCP_ERROR_CODES.INVALID_REQUEST,
            hint: "Pass exactly one search mode.",
        });
    };
}
function normalizeLocator(raw, args) {
    const r = (raw ?? {});
    // For the by-formId path, the caller passed `file` + `formId` directly — those
    // are the canonical locator identity and should round-trip unchanged (including
    // the caller's 0x prefix style). The daemon's echoed values may have the prefix
    // stripped because we strip it at the edge. Prefer caller-supplied values for
    // identity fields; fall back to daemon for signature/editorId which the caller
    // does not supply on the formId path.
    return {
        file: args.file ?? r.file,
        formId: args.formId ?? r.formId,
        signature: r.signature,
        editorId: args.editorId ?? r.editorId,
    };
}
//# sourceMappingURL=find-record.js.map