import { z } from "zod";
import type { DaemonAdapter } from "../daemon-adapter.js";
import type { AuditLogger } from "../audit.js";
import type { Registry } from "../rules/registry.js";
import type { Envelope, ToolContext } from "../types.js";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { emitAudit } from "../audit-line.js";

// r6 supports.reverseNavigation (contract 0.19) + supports.childGroupNavigation
// (contract 0.13). The daemon now answers `includeParents: true` on records.get,
// records.find_by_form_id, and records.find_by_editor_id, returning a
// `relations.parents` array (nearest-first, depth cap 16).
//
// This wrapper forces `includeParents: true` and flattens the ancestry into a
// flat `ancestors` list so the agent sees one clean tree instead of having to
// drill into relations.parents from a multi-field record envelope.

const ByFormId = z.object({
  file: z.string().min(1),
  formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
});
const ByEditorId = z.object({
  editorId: z.string().min(1),
  signature: z.string().optional(),
});

/** Returns args with `formId` stripped of any leading "0x" prefix. */
function stripFormIdPrefix(args: Record<string, unknown>): Record<string, unknown> {
  if (typeof args.formId !== "string") return args;
  const f = args.formId;
  return f.startsWith("0x") || f.startsWith("0X") ? { ...args, formId: f.slice(2) } : args;
}

export interface NavigateAncestryOptions {
  adapter: DaemonAdapter;
  registry: Registry;
  audit: AuditLogger;
  getContext: () => ToolContext | undefined;
}

export function makeNavigateAncestryHandler(opts: NavigateAncestryOptions) {
  return async (args: Record<string, unknown>): Promise<Envelope> => {
    const ctx = opts.getContext();
    if (!ctx) {
      return refuse({
        tool: "xedit_navigate_ancestry",
        summary: "Session not established",
        code: MCP_ERROR_CODES.STATE_VIOLATION,
        hint: "Call xedit_session first.",
      });
    }

    // Placeholder-aware mode detection (mirrors find-record.ts). OpenAI-style
    // tool callers often fill every declared property with a placeholder; treat
    // empty file or all-zero formId as "not in formId mode" when an editorId is
    // also supplied.
    const fileRaw = typeof args.file === "string" ? args.file.trim() : "";
    const formIdRaw = typeof args.formId === "string" ? args.formId.trim() : "";
    const editorIdRaw = typeof args.editorId === "string" ? args.editorId.trim() : "";
    const signatureRaw =
      typeof args.signature === "string" && args.signature.trim().length > 0
        ? args.signature.trim()
        : undefined;

    const formIdMatchesPattern = /^(0x)?[0-9a-fA-F]{1,8}$/.test(formIdRaw);
    const formIdIsAllZero = /^(0x)?0+$/i.test(formIdRaw);
    const fileLooksReal = fileRaw.length > 0;
    const formIdLooksReal = formIdRaw.length > 0 && formIdMatchesPattern && !formIdIsAllZero;
    const editorIdLooksReal = editorIdRaw.length > 0;

    const fileFormIdMode = fileLooksReal && formIdLooksReal;
    const editorIdMode = editorIdLooksReal;

    let modeArgs: Record<string, unknown>;
    let command: string;
    let modeLabel: string;

    if (fileFormIdMode) {
      const parsed = ByFormId.safeParse({ file: fileRaw, formId: formIdRaw });
      if (!parsed.success) {
        const env = refuse({
          tool: "xedit_navigate_ancestry",
          summary: "Argument validation failed",
          code: MCP_ERROR_CODES.INVALID_REQUEST,
          hint: "Provide either {file, formId} or {editorId} with valid values.",
          detail: { issues: parsed.error.issues },
        });
        await emitAudit({ audit: opts.audit, tool: "xedit_navigate_ancestry", args, env, ctx });
        return env;
      }
      modeArgs = stripFormIdPrefix({
        file: parsed.data.file,
        formId: parsed.data.formId,
        includeParents: true,
      });
      // Prefer records.get over records.find_by_form_id here: the agent
      // already has the locator, and records.get returns the full record
      // envelope plus relations.parents in one round-trip.
      command = "records.get";
      modeLabel = `${parsed.data.file}/${parsed.data.formId}`;
    } else if (editorIdMode) {
      const bArgs: Record<string, unknown> = { editorId: editorIdRaw };
      if (signatureRaw !== undefined) bArgs.signature = signatureRaw;
      const parsed = ByEditorId.safeParse(bArgs);
      if (!parsed.success) {
        const env = refuse({
          tool: "xedit_navigate_ancestry",
          summary: "Argument validation failed",
          code: MCP_ERROR_CODES.INVALID_REQUEST,
          hint: "Provide either {file, formId} or {editorId} with valid values.",
          detail: { issues: parsed.error.issues },
        });
        await emitAudit({ audit: opts.audit, tool: "xedit_navigate_ancestry", args, env, ctx });
        return env;
      }
      modeArgs = { ...parsed.data, includeParents: true };
      command = "records.find_by_editor_id";
      modeLabel = `editor:${parsed.data.editorId}`;
    } else {
      const env = refuse({
        tool: "xedit_navigate_ancestry",
        summary: "Provide either {file, formId} or {editorId}",
        code: MCP_ERROR_CODES.INVALID_REQUEST,
        hint:
          "Pass exactly one mode: { file: 'Plugin.esp', formId: '00ABCDEF' } OR { editorId: 'SomeEDID', signature?: 'QUST' }.",
      });
      await emitAudit({ audit: opts.audit, tool: "xedit_navigate_ancestry", args, env, ctx });
      return env;
    }

    const p = precheck(
      { tool: "xedit_navigate_ancestry", args: modeArgs },
      { ctx, needs: { daemon: true } },
    );
    if (p) {
      await emitAudit({ audit: opts.audit, tool: "xedit_navigate_ancestry", args, env: p, ctx });
      return p;
    }

    const r = await runRules({
      tool: "xedit_navigate_ancestry",
      args: modeArgs,
      ctx,
      registry: opts.registry,
    });
    if (r.refusal) {
      await emitAudit({
        audit: opts.audit,
        tool: "xedit_navigate_ancestry",
        args,
        env: r.refusal,
        ctx,
        ruleHits: r.ruleHits,
      });
      return r.refusal;
    }

    const native = await opts.adapter.call({ command, args: modeArgs });
    if (!native.ok) {
      const env = refuse({
        tool: "xedit_navigate_ancestry",
        summary: `${command} failed: ${native.error.code}`,
        code: MCP_ERROR_CODES.DAEMON_ERROR,
        hint: native.error.message,
        detail: { daemonCode: native.error.code, daemonDetails: native.error.details },
      });
      await emitAudit({ audit: opts.audit, tool: "xedit_navigate_ancestry", args, env, ctx });
      return env;
    }

    const ancestors = extractAncestors(native.result, command);
    const env = okEnv({
      tool: "xedit_navigate_ancestry",
      summary: `ancestry for ${modeLabel}: ${ancestors.length} ancestor${ancestors.length === 1 ? "" : "s"}`,
      status: "completed",
      data: {
        ancestors,
        depth: ancestors.length,
      },
      warnings: r.warnings,
    });
    await emitAudit({
      audit: opts.audit,
      tool: "xedit_navigate_ancestry",
      args,
      env,
      ctx,
      ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
    });
    return env;
  };
}

/**
 * Extract a flat `ancestors` list from the daemon response.
 *
 * For records.get: result.relations.parents (nearest-first, depth cap 16).
 * For records.find_by_editor_id: hits[0].object.relations.parents (uses first match).
 * Older mocks may return relations.parents directly at the top level.
 */
function extractAncestors(result: unknown, command: string): Array<Record<string, unknown>> {
  if (!result || typeof result !== "object") return [];
  const r = result as Record<string, unknown>;

  if (command === "records.find_by_editor_id") {
    const hits = Array.isArray(r.hits) ? r.hits : Array.isArray(r.matches) ? r.matches : [];
    if (hits.length === 0) return [];
    const first = hits[0] as Record<string, unknown>;
    const object = first.object && typeof first.object === "object" ? (first.object as Record<string, unknown>) : first;
    return ancestorsFrom(object);
  }
  return ancestorsFrom(r);
}

function ancestorsFrom(node: Record<string, unknown>): Array<Record<string, unknown>> {
  const relations =
    node.relations && typeof node.relations === "object"
      ? (node.relations as Record<string, unknown>)
      : null;
  const candidates = [
    relations?.parents,
    node.parents,
    node.ancestors, // tolerate pre-r6 stub shape
  ];
  for (const c of candidates) {
    if (Array.isArray(c)) {
      return c.map(normalizeAncestor).filter((a): a is Record<string, unknown> => a !== null);
    }
  }
  return [];
}

function normalizeAncestor(entry: unknown): Record<string, unknown> | null {
  if (!entry || typeof entry !== "object") return null;
  const e = entry as Record<string, unknown>;
  // Surface the most-commonly-needed fields at the top level. The daemon may
  // wrap as { locator: {file, formId, path}, object: {signature, editorId} } or
  // return a flat object. Unify to { locator, signature?, editorId?, formId, file }.
  const locator = e.locator && typeof e.locator === "object" ? (e.locator as Record<string, unknown>) : null;
  const object = e.object && typeof e.object === "object" ? (e.object as Record<string, unknown>) : null;
  const merged: Record<string, unknown> = { ...(object ?? {}), ...(locator ?? {}) };
  // If no nesting was present, treat the entry itself as the flat ancestor.
  if (!locator && !object) {
    return { ...e };
  }
  // Preserve the original locator if it was nested (audits often want it).
  if (locator) merged.locator = locator;
  return merged;
}
