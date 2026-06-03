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

    // Mode detection must be PLACEHOLDER-AWARE, not just Zod-strict. OpenCode
    // and other OpenAI-style tool-calling backends frequently send placeholder
    // values for "unused" declared schema fields because the model has been
    // trained to fill every declared property. Real-world envelope shapes
    // observed against this wrapper:
    //
    //   {file: "Kinggath Placeholder Should Be Ignored", formId: "0",
    //    editorId: "kgcShip_QUST_Manager_Main", signature: "QUST"}
    //
    //   {file: "kinggathcreations_spaceship.esm", formId: "0",
    //    editorId: "kgcShip_PACK_ShipFollowPackage_Short", signature: "PACK"}
    //
    // Both validate ByFormId because file passes min(1) and formId="0" matches
    // the FormID regex. A naive raw-Zod router would pick mode A and either
    // hit LOAD001 (bogus file) or echo a fake-positive locator (real file,
    // FormID 0 doesn't exist as a meaningful record).
    //
    // Treat formId as a placeholder when it is all-zero ("0", "00", "0x0",
    // "00000000", "0x00000000", ...). Treat file as a placeholder when it is
    // empty after trimming. When the placeholder pattern is present AND a
    // non-empty editorId is supplied, route to EditorId mode and discard the
    // placeholder file/formId.
    //
    // file+formId mode still wins when BOTH look like real lookup values,
    // matching the documented "if both are supplied, {file, formId} wins"
    // semantic.
    const fileRaw = typeof args.file === "string" ? args.file.trim() : "";
    const formIdRaw = typeof args.formId === "string" ? args.formId.trim() : "";
    const editorIdRaw = typeof args.editorId === "string" ? args.editorId.trim() : "";
    const signatureRaw = typeof args.signature === "string" && args.signature.trim().length > 0
      ? args.signature.trim()
      : undefined;

    const formIdMatchesPattern = /^(0x)?[0-9a-fA-F]{1,8}$/.test(formIdRaw);
    const formIdIsAllZero = /^(0x)?0+$/i.test(formIdRaw);
    const fileLooksReal = fileRaw.length > 0;
    const formIdLooksReal = formIdRaw.length > 0 && formIdMatchesPattern && !formIdIsAllZero;
    const editorIdLooksReal = editorIdRaw.length > 0;

    const fileFormIdMode = fileLooksReal && formIdLooksReal;
    const editorIdMode = editorIdLooksReal;

    if (fileFormIdMode) {
      const aResult = ByFormId.safeParse({ file: fileRaw, formId: formIdRaw });
      if (!aResult.success) {
        // Pattern matched but Zod rejected — fall through to refusal below.
      } else {
        const daemonArgs = stripFormIdPrefix({ file: aResult.data.file, formId: aResult.data.formId });
        // Load-order check is owned by LOAD001 (rule layer) for uniform behavior
        // across all record-side tools; pipeline runs rules against the
        // post-projection daemonArgs, so LOAD001 sees the cleaned `file`.
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
    }

    if (editorIdMode) {
      const bArgs: Record<string, unknown> = { editorId: editorIdRaw };
      if (signatureRaw !== undefined) bArgs.signature = signatureRaw;
      const bResult = ByEditorId.safeParse(bArgs);
      if (bResult.success) {
        // For EditorId mode the daemon expects only {editorId, signature?}; do
        // NOT forward stray file/formId placeholders the caller may have set.
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
    }

    return refuse({
      tool: "xedit_find_record",
      summary: "Provide either {file, formId} or {editorId}",
      code: MCP_ERROR_CODES.INVALID_REQUEST,
      hint:
        "Pass exactly one mode: { file: 'Plugin.esp', formId: '00ABCDEF' } OR { editorId: 'SomeEDID', signature?: 'QUST' }. " +
        "Empty file, missing formId, or an all-zero formId placeholder is not a valid {file, formId} call.",
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
