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

    if (typeof args.formId === "string" && typeof args.file === "string") {
      const daemonArgs = stripFormIdPrefix(args);
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_form_id",
          needs: { daemon: true, targetFileFromArg: "file" },
          shape: (result) => ({ locators: [normalizeLocator(result, args)] }),
        },
        { args: daemonArgs, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }

    if (typeof args.editorId === "string") {
      return runTool(
        {
          ...findRecordSpec,
          command: "records.find_by_editor_id",
          shape: (result) => {
            const matches = (result as { matches?: unknown[] }).matches ?? [];
            return { locators: matches.map((m) => normalizeLocator(m, args)) };
          },
        },
        { args, ctx, adapter: opts.adapter, registry: opts.registry, audit: opts.audit },
      );
    }

    return refuse({
      tool: "xedit_find_record",
      summary: "Provide either {file, formId} or {editorId}",
      code: MCP_ERROR_CODES.INVALID_REQUEST,
      hint: "Pass exactly one search mode.",
    });
  };
}

function normalizeLocator(raw: unknown, args: Record<string, unknown>): Record<string, unknown> {
  const r = (raw ?? {}) as Record<string, unknown>;
  return {
    file: r.file ?? args.file,
    formId: r.formId ?? args.formId,
    signature: r.signature,
    editorId: r.editorId ?? args.editorId,
  };
}
