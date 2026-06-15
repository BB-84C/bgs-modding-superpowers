/**
 * mo2_backup_profile — T2 explicit profile-level snapshot.
 *
 * Copies all .txt + .ini under <profile>/ to a labeled backup dir under
 * <MO2_Root>/.mo2-mcp/profile-backups/. Default label is timestamp.
 */
import { z } from "zod";
import { copyFile, mkdir, readdir } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { resolveProfileDir } from "../path-helpers.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        profile: z.string().default("Default"),
        label: z.string().optional(),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
function _timestampLabel() {
    return new Date().toISOString().replace(/[:.]/g, "-");
}
function _backupDir(ctx, profile, label) {
    return join(ctx.config.mo2Root, ".mo2-mcp", "profile-backups", `${profile}_${label}`);
}
const handler = {
    toolName: "mo2_backup_profile",
    async buildPlan(args, ctx) {
        const profile = args.profile ?? "Default";
        const profileDir = resolveProfileDir(ctx, profile);
        const label = args.label ?? _timestampLabel();
        const backupDir = _backupDir(ctx, profile, label);
        const filesToCopy = ["modlist.txt", "plugins.txt", "loadorder.txt", "settings.txt"];
        return {
            diff: `cp ${filesToCopy.join(", ")} from ${profileDir} → ${backupDir}`,
            affectedFiles: [backupDir],
            targets: filesToCopy.map((f) => ({
                path: join(profileDir, f),
                kind: "text-file",
            })),
        };
    },
    async applyMutation(plan, ctx) {
        const profile = plan.args.profile ?? "Default";
        const profileDir = resolveProfileDir(ctx, profile);
        const label = plan.args.label ?? _timestampLabel();
        const backupDir = _backupDir(ctx, profile, label);
        await mkdir(backupDir, { recursive: true });
        const allFiles = await readdir(profileDir);
        const copied = [];
        for (const f of allFiles) {
            if (f.endsWith(".txt") || f.endsWith(".ini")) {
                try {
                    await copyFile(join(profileDir, f), join(backupDir, f));
                    copied.push(f);
                }
                catch {
                    // skip unreadable
                }
            }
        }
        return {
            backup_label: label,
            backup_dir: backupDir,
            files_backed_up: copied.length,
            files: copied,
        };
    },
};
registerTool({
    name: "mo2_backup_profile",
    tier: "T2",
    description: "Explicit full-profile backup (all .txt + .ini under profile). Saved to .mo2-mcp/profile-backups/<profile>_<label>/. Default label = timestamp.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
