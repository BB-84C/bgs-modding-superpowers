/**
 * mo2_edit_meta — T2 plan/apply arbitrary meta.ini field edits.
 *
 * updates schema: { section: { key: value } } — merge semantics (existing
 * sections + keys preserved unless explicitly overridden).
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { resolveModMetaPath } from "../path-helpers.js";
import { upsertIniValue } from "../ini-helpers.js";
import { requireBoundContext } from "../binding.js";
import { logApplyEvent } from "../log-apply.js";

// BUG-10 fix (2026-06-17): name + plan_id + lease_token gain .min(1). `updates`
// keys/values are arbitrary INI section/value pairs and may legitimately be
// empty strings (clearing an existing key), so the nested z.string() schemas
// stay permissive.
const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string().min(1),
    updates: z.record(z.record(z.string())),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

const handler: PlanApplyHandler = {
  toolName: "mo2_edit_meta",
  async buildPlan(args, ctx) {
    const metaPath = await resolveModMetaPath(args.name as string, ctx);
    const updates = args.updates as Record<string, Record<string, string>>;
    const diff = Object.entries(updates)
      .map(
        ([s, kv]) =>
          `[${s}]\n${Object.entries(kv)
            .map(([k, v]) => `${k}=${v}`)
            .join("\n")}`,
      )
      .join("\n\n");
    return {
      diff,
      affectedFiles: [metaPath],
      targets: [{ path: metaPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const updates = args.updates as Record<string, Record<string, string>>;
    const metaPath = await resolveModMetaPath(args.name as string, ctx);
    const bound = requireBoundContext(ctx);
    const pipeClient = bound.pipeClient;
    if (pipeClient) {
      const resp = await pipeClient.call("mods.meta_write", {
        name: args.name,
        updates,
      });
      if (resp.ok) {
        await logApplyEvent(
          handler.toolName,
          `edited meta of "${args.name as string}" sections=${Object.keys(updates).join(",")}`,
          bound,
          plan.planId,
          "",
        );
        return resp.result as Record<string, unknown>;
      }
      // BUG-23 (issue #12) fix (2026-06-25): stale-broker deploys lack the
      // mods.meta_write handler that exists in source. Gracefully fall
      // through to the offline atomic INI rewrite below instead of bombing
      // the whole apply. Real broker errors (lock contention, missing mod,
      // etc.) still surface — only method_not_found triggers the fallback.
      // The offline path's only semantic gap vs. broker is the
      // modDataChanged signal MO2 picks up on its next refresh anyway.
      if (resp.error?.code !== "method_not_found") {
        throw new Error(resp.error?.message ?? "broker error");
      }
      warnStaleMetaWriteBroker();
    }
    let text = "";
    try {
      text = await readFile(metaPath, "utf8");
    } catch {
      // create
    }
    for (const [section, kv] of Object.entries(updates)) {
      for (const [k, v] of Object.entries(kv)) {
        text = upsertIniValue(text, section, k, String(v));
      }
    }
    await atomicWriteText(metaPath, text);
    await logApplyEvent(
      handler.toolName,
      `edited meta of "${args.name as string}" sections=${Object.keys(updates).join(",")}`,
      bound,
      plan.planId,
      "",
    );
    return {
      name: args.name,
      sections_updated: Object.keys(updates),
      source: pipeClient ? "offline_fallback_stale_broker" : "offline",
    };
  },
};

let META_WRITE_STALE_WARNED = false;

function warnStaleMetaWriteBroker(): void {
  if (META_WRITE_STALE_WARNED) return;
  META_WRITE_STALE_WARNED = true;
  process.stderr.write(
    "[mo2-mcp] broker lacks 'mods.meta_write' handler; falling through to offline INI rewrite. " +
      "Consider redeploying via tools/mo2-control-plane/install-mo2-control-plane.ps1 " +
      "and restarting MO2.\n",
  );
}

/** @internal test-only reset for the dedup'd warning state. */
export function _resetMetaWriteStaleWarnedForTests(): void {
  META_WRITE_STALE_WARNED = false;
}

registerTool({
  name: "mo2_edit_meta",
  tier: "T2",
  description:
    "Edit arbitrary meta.ini fields. updates = {section: {key: value}}. Plan returns diff; apply atomically merges.",
  inputSchema,
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
