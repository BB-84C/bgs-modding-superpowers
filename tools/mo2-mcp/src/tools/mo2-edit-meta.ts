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
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string(),
    updates: z.record(z.record(z.string())),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
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
    const pipeClient = requireBoundContext(ctx).pipeClient;
    if (pipeClient) {
      const resp = await pipeClient.call("mods.meta_write", {
        name: args.name,
        updates,
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      return resp.result as Record<string, unknown>;
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
    return { name: args.name, sections_updated: Object.keys(updates), source: "offline" };
  },
};

registerTool({
  name: "mo2_edit_meta",
  tier: "T2",
  description:
    "Edit arbitrary meta.ini fields. updates = {section: {key: value}}. Plan returns diff; apply atomically merges.",
  inputSchema,
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
