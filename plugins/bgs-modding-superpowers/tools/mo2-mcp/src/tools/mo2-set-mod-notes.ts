/**
 * mo2_set_mod_notes — T2 plan/apply.
 *
 * Sets meta.ini [General] notes="..." atomically. Live mode uses broker
 * mods.meta_write; offline mode atomically writes the file.
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { resolveModMetaPath } from "../path-helpers.js";
import { upsertIniValue } from "../ini-helpers.js";

const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), name: z.string(), notes: z.string() }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

const handler: PlanApplyHandler = {
  toolName: "mo2_set_mod_notes",
  async buildPlan(args, ctx) {
    const metaPath = await resolveModMetaPath(args.name as string, ctx);
    return {
      diff: `[General]\nnotes="${args.notes}"`,
      affectedFiles: [metaPath],
      targets: [{ path: metaPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const metaPath = await resolveModMetaPath(args.name as string, ctx);
    if (ctx.pipeClient) {
      const resp = await ctx.pipeClient.call("mods.meta_write", {
        name: args.name,
        updates: { General: { notes: `"${args.notes}"` } },
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      return resp.result as Record<string, unknown>;
    }
    // Offline: atomic write
    let text = "";
    try {
      text = await readFile(metaPath, "utf8");
    } catch {
      // create new
    }
    text = upsertIniValue(text, "General", "notes", `"${args.notes}"`);
    await atomicWriteText(metaPath, text);
    return { name: args.name, notes_set: true, source: "offline" };
  },
};

registerTool({
  name: "mo2_set_mod_notes",
  tier: "T2",
  description:
    "Set mod notes (meta.ini [General] notes=). Plan returns diff; apply atomically writes via temp+rename or broker mods.meta_write.",
  inputSchema,
  handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
