import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { runTool, type ToolSpec } from "../pipeline/compose.js";
import { refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";

const ByFormId = z.object({
  file: z.string().min(1),
  // Accept both "0x0000003C" and bare "0000003C" — the daemon wants no 0x prefix; we
  // strip it before forwarding so agents can use either style.
  formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});

/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args: Record<string, unknown>): Record<string, unknown> {
  if (typeof args.formId !== "string") return args;
  const f = args.formId;
  return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}
const ByEditorId = z.object({
  editorId: z.string().min(1),
  signature: z.string().optional(),
});

export const findRecordSpec: ToolSpec = {
  name: "xedit_find_record",
  schema: z.union([ByFormId, ByEditorId]),
  needs: { daemon: true },
  command: "records.find_by_form_id",
  summary: (a) =>
    a.formId ? `find ${String(a.formId)} in ${String(a.file)}` : `find editor ${String(a.editorId)}`,
};

export interface FindRecordOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeFindRecordHandler(opts: FindRecordOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_find_record",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }

    // Mode detection MUST use the strict Zod branches so empty strings and
    // missing fields are rejected up front. The previous `typeof === "string"`
    // shortcut accepted file:"" + formId:"00000000" placeholders that some
    // clients send when they treat declared schema properties as required,
    // and then routed those placeholders into records.find_by_form_id —
    // producing a fake "found" locator that echoed the placeholder args back
    // to the caller. See OpenCode envelope reproduction 2026-06-03.
    const aResult = ByFormId.safeParse(args);
    const bResult = ByEditorId.safeParse(args);
    const aValid = aResult.success;
    const bValid = bResult.success;

    if (aValid) {
      // FormId mode wins over EditorId mode when both branches validate,
      // matching the documented "if both are supplied, {file, formId} wins"
      // semantic from the tool description.
      const daemonArgs = stripFormIdPrefix({ file: aResult.data.file, formId: aResult.data.formId });
      // Load-order check is owned by LOAD001 (rule layer) for uniform behavior
      // across all record-side tools; pipeline runs rules against the ORIGINAL
      // caller args, so LOAD001 still sees `file` as the caller passed it.
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_form_id",
          needs: { daemon: true },
          shape: (result) => ({ locators: [normalizeLocator(result, aResult.data)] }),
        },
        { args: daemonArgs, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }

    if (bValid) {
      // For EditorId mode the daemon expects only {editorId, signature?}; do
      // not forward stray file/formId placeholders the caller may have set.
      const daemonArgs: Record<string, unknown> = { editorId: bResult.data.editorId };
      if (bResult.data.signature !== undefined) daemonArgs.signature = bResult.data.signature;
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_editor_id",
          shape: (result) => {
            // The live daemon returns { hits: [{ locator, object }], count, truncated }
            // for records.find_by_editor_id (see daemon xeAutomationCommandsRecords);
            // older mocks and pre-contract responses returned { matches: [{...}] }.
            // Accept both shapes so the wrapper does not lose the daemon's real
            // locator data (file, formId) when projecting hits.
            const r = (result ?? {}) as {
              hits?: unknown[];
              matches?: unknown[];
            };
            const entries = Array.isArray(r.hits) ? r.hits : Array.isArray(r.matches) ? r.matches : [];
            return { locators: entries.map((entry) => normalizeLocator(unwrapHit(entry), bResult.data)) };
          },
        },
        { args: daemonArgs, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }

    return refuse({
      tool: "xedit_find_record",
      summary: "Provide either {file, formId} or {editorId}",
      code: MCP_ERROR_CODES.INVALID_REQUEST,
      hint:
        "Pass exactly one mode: { file: 'Plugin.esp', formId: '00ABCDEF' } OR { editorId: 'SomeEDID', signature?: 'QUST' }. " +
        "Empty-string file or missing formId is not a valid {file, formId} call.",
    });
  };
}

/**
 * The live daemon's find_by_editor_id wraps each hit as { locator, object },
 * where `locator` carries `{ file, formId, path }` and `object` carries the
 * record fields (signature, editorId, isWinningOverride, ...). Older response
 * shapes returned the flat record directly. Unwrap to a single object that
 * carries both locator identity and record fields, with the locator taking
 * precedence for file/formId so identity round-trips cleanly.
 */
function unwrapHit(entry: unknown): Record<string, unknown> {
  if (entry === null || typeof entry !== "object") return {};
  const e = entry as Record<string, unknown>;
  const hasLocator = e.locator && typeof e.locator === "object";
  const hasObject = e.object && typeof e.object === "object";
  if (!hasLocator && !hasObject) return e;
  const locator = (hasLocator ? (e.locator as Record<string, unknown>) : {}) ?? {};
  const object = (hasObject ? (e.object as Record<string, unknown>) : {}) ?? {};
  return { ...object, ...locator };
}

function normalizeLocator(raw: unknown, args: Record<string, unknown>): Record<string, unknown> {
  const r = (raw ?? {}) as Record<string, unknown>;
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
