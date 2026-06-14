/**
 * mo2_restore_profile — T3 restore profile state from named backup label.
 *
 * Counterpart to mo2_backup_profile (S4.5). Copies all files from
 * <MO2_Root>/.mo2-mcp/profile-backups/<profile>_<label>/ back into the
 * profile directory.
 */
import { z } from "zod";
import { copyFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { resolveProfileDir } from "../path-helpers.js";

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    profile: z.string().default("Default"),
    label: z.string(),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

function _backupDir(ctx: { config: { mo2Root: string } }, profile: string, label: string): string {
  return join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${profile}_${label}`);
}

const handler: PlanApplyHandler = {
  toolName: "mo2_restore_profile",
  async buildPlan(args, ctx) {
    const profile = (args.profile as string) ?? "Default";
    const label = args.label as string;
    const backupDir = _backupDir(ctx, profile, label);
    const files = await readdir(backupDir).catch(() => {
      throw new Error(`backup_not_found: ${profile}_${label}`);
    });
    const profileDir = resolveProfileDir(ctx, profile);
    return {
      diff: `Restore ${files.length} files from ${backupDir} → ${profileDir}`,
      affectedFiles: files.map((f) => join(profileDir, f)),
      targets: files.map((f) => ({ path: join(profileDir, f), kind: "text-file" as const })),
    };
  },
  async applyMutation(plan, ctx) {
    const profile = (plan.args.profile as string) ?? "Default";
    const label = plan.args.label as string;
    const backupDir = _backupDir(ctx, profile, label);
    const profileDir = resolveProfileDir(ctx, profile);
    const files = await readdir(backupDir);
    const restored: string[] = [];
    const failed: string[] = [];
    for (const f of files) {
      try {
        await copyFile(join(backupDir, f), join(profileDir, f));
        restored.push(f);
      } catch {
        failed.push(f);
      }
    }
    return { profile, label, restored, failed };
  },
};

registerTool({
  name: "mo2_restore_profile",
  tier: "T3",
  description:
    "Restore profile state from a mo2_backup_profile label. Plan returns file count; apply copies all backed-up files back over profile.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
