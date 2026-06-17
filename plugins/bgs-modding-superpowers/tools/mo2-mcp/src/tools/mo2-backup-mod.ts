/**
 * mo2_backup_mod — T2 file-level mod backup.
 *
 * Pattern (librarian §A7): copy mods/<name> → mods/<name>backup<N>, where N
 * is the first free slot. MO2 auto-tags FLAG_BACKUP via regex `.*backup[0-9]*`
 * (verbatim from MO2 source `modinfo.cpp:69-72`).
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { cp } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { resolveModsDir } from "../path-helpers.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): mod name + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), name: z.string().min(1) }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

const handler: PlanApplyHandler = {
  toolName: "mo2_backup_mod",
  async buildPlan(args, ctx) {
    const modsDir = await resolveModsDir(ctx);
    const sourceMod = join(modsDir, args.name as string);
    if (!existsSync(sourceMod)) {
      throw new Error(`mod_not_found: ${args.name}`);
    }
    let i = 0;
    while (existsSync(join(modsDir, `${args.name}backup${i}`))) i++;
    const backupPath = join(modsDir, `${args.name}backup${i}`);
    return {
      diff: `cp -r ${sourceMod} → ${backupPath}`,
      affectedFiles: [backupPath],
      targets: [{ path: sourceMod, kind: "directory" }],
    };
  },
  async applyMutation(plan, ctx) {
    const modsDir = await resolveModsDir(ctx);
    const sourceMod = join(modsDir, plan.args.name as string);
    let i = 0;
    while (existsSync(join(modsDir, `${plan.args.name}backup${i}`))) i++;
    const backupPath = join(modsDir, `${plan.args.name}backup${i}`);
    await cp(sourceMod, backupPath, { recursive: true });
    const pipeClient = requireBoundContext(ctx).pipeClient;
    if (pipeClient) {
      // Refresh MO2 so it picks up the new backup mod (auto-tags FLAG_BACKUP)
      await pipeClient.call("organizer.refresh", { save_changes: false }).catch(() => {});
    }
    return { backup_name: `${plan.args.name}backup${i}`, backup_path: backupPath };
  },
};

registerTool({
  name: "mo2_backup_mod",
  tier: "T2",
  description:
    "Create file-level mod backup (<name>backupN naming; MO2 auto-tags FLAG_BACKUP). Plan returns backup path; apply does the recursive copy.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
