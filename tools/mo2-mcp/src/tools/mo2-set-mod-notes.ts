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
import { requireBoundContext, bindingSnapshot } from "../binding.js";
import { logApplyEvent } from "../log-apply.js";

// BUG-10 fix (2026-06-17): name + plan_id + lease_token gain .min(1). `notes`
// stays a free-form string — clearing notes to empty is a legitimate use.
const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), name: z.string().min(1), notes: z.string() }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
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
    const bound = requireBoundContext(ctx);
    const pipeClient = bound.pipeClient;
    if (pipeClient) {
      const resp = await pipeClient.call("mods.meta_write", {
        name: args.name,
        updates: { General: { notes: `"${args.notes}"` } },
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      await logApplyEvent(
        handler.toolName,
        `set notes of "${args.name as string}" (length=${String(args.notes).length})`,
        bound,
        plan.planId,
        "",
      );
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
    await logApplyEvent(
      handler.toolName,
      `set notes of "${args.name as string}" (length=${String(args.notes).length})`,
      bound,
      plan.planId,
      "",
    );
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
