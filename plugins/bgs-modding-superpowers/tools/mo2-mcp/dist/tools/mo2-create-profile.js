/**
 * mo2_create_profile — T3 create profile with online initialize when available.
 *
 * Online path calls broker profile.initialize, which wraps
 * IPluginGame.initializeProfile. Offline fallback creates the profile directory
 * and minimal profile text files but cannot synthesize game INI defaults.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { mkdir, writeFile, copyFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { requireBoundContext } from "../binding.js";
import { logApplyEvent } from "../log-apply.js";
const ProfileSettingSchema = z.enum(["MODS", "SAVEGAMES", "CONFIGURATION", "PREFER_DEFAULTS"]);
// BUG-10 fix (2026-06-17): profile name + plan_id + lease_token gain .min(1).
// from_profile stays optional (clone source is allowed to be omitted).
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string().min(1),
        from_profile: z.string().optional(),
        settings: z.array(ProfileSettingSchema).optional(),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);
async function _copyProfileTextAndIni(profilesRoot, fromProfile, newDir) {
    const srcDir = join(profilesRoot, fromProfile);
    const files = await readdir(srcDir).catch(() => []);
    for (const file of files) {
        if (!file.endsWith(".txt") && !file.endsWith(".ini"))
            continue;
        try {
            await copyFile(join(srcDir, file), join(newDir, file));
        }
        catch {
            // Best-effort clone: tolerate profile-specific files being locked/missing.
        }
    }
}
const handler = {
    toolName: "mo2_create_profile",
    async buildPlan(args, ctx) {
        const bound = requireBoundContext(ctx);
        const name = args.name;
        const profilesRoot = join(bound.config.mo2Root, "profiles");
        const newDir = join(profilesRoot, name);
        if (existsSync(newDir))
            throw new Error(`profile_exists: ${name}`);
        const path = bound.pipeClient ? "online" : "offline";
        return {
            diff: `Create profile ${name} via ${path} path${args.from_profile ? `, clone modlist from ${String(args.from_profile)}` : ""}`,
            affectedFiles: [newDir],
            targets: [],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const name = plan.args.name;
        const profilesRoot = join(bound.config.mo2Root, "profiles");
        const newDir = join(profilesRoot, name);
        await mkdir(newDir, { recursive: true });
        await writeFile(join(newDir, "modlist.txt"), "", "utf8");
        await writeFile(join(newDir, "archives.txt"), "", "utf8");
        let source = bound.pipeClient
            ? "online_initialized"
            : "offline_created";
        let warning;
        if (bound.pipeClient) {
            try {
                const resp = await bound.pipeClient.call("profile.initialize", {
                    profile_dir: newDir,
                    settings: plan.args.settings ?? ["MODS", "CONFIGURATION"],
                });
                if (!resp.ok)
                    throw new Error(resp.error?.message ?? "profile.initialize failed");
            }
            catch (e) {
                source = "online_init_failed_offline_fallback";
                warning = e instanceof Error ? e.message : String(e);
            }
        }
        if (typeof plan.args.from_profile === "string") {
            await _copyProfileTextAndIni(profilesRoot, plan.args.from_profile, newDir);
        }
        await logApplyEvent(handler.toolName, `created profile "${name}" settings=${(plan.args.settings ?? []).join(",")}`, bound, plan.planId, name);
        return {
            profile_name: name,
            path: newDir,
            source,
            ...(warning ? { warning } : {}),
        };
    },
};
registerTool({
    name: "mo2_create_profile",
    tier: "T3",
    description: "Create a new profile. Online: broker calls IPluginGame.initializeProfile. Offline: filesystem-only create (no game INI defaults). Optional from_profile clones modlist+plugins from existing profile.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
