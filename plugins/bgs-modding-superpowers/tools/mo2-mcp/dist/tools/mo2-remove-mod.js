/**
 * mo2_remove_mod — T3 destructive mod removal.
 *
 * Default-safe destructive path: backup_first defaults to true and creates a
 * file-level <name>backup<N> copy before deleting/removing the mod.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { cp, rm, readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { resolveModsDir } from "../path-helpers.js";
import { atomicWriteText } from "../atomic.js";
import { invalidateWorld } from "./state-sync.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({ mode: z.literal("plan"), name: z.string(), backup_first: z.boolean().default(true) }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
function _lineReferencesMod(line, modName) {
    return line.replace(/^[+\-]/, "") === modName;
}
async function _nextBackupName(modsDir, name) {
    let i = 0;
    while (existsSync(join(modsDir, `${name}backup${i}`)))
        i++;
    return `${name}backup${i}`;
}
async function _scrubAllProfileModlists(mo2Root, name) {
    const profilesRoot = join(mo2Root, "profiles");
    const profiles = await readdir(profilesRoot).catch(() => []);
    const updated = [];
    for (const profile of profiles) {
        const modlistPath = join(profilesRoot, profile, "modlist.txt");
        try {
            const text = await readFile(modlistPath, "utf8");
            const filtered = text
                .split(/\r?\n/)
                .filter((line) => !_lineReferencesMod(line, name))
                .join("\n");
            if (filtered !== text) {
                await atomicWriteText(modlistPath, filtered);
                updated.push(profile);
            }
        }
        catch {
            // Skip non-profile dirs or unreadable modlists.
        }
    }
    return updated;
}
async function _profilesReferencingMod(mo2Root, name) {
    const profilesRoot = join(mo2Root, "profiles");
    const profiles = await readdir(profilesRoot).catch(() => []);
    const referenced = [];
    for (const profile of profiles) {
        const modlistPath = join(profilesRoot, profile, "modlist.txt");
        try {
            const text = await readFile(modlistPath, "utf8");
            if (text.split(/\r?\n/).some((line) => _lineReferencesMod(line, name))) {
                referenced.push(profile);
            }
        }
        catch {
            // Skip non-profile dirs or unreadable modlists.
        }
    }
    return referenced.sort();
}
const handler = {
    toolName: "mo2_remove_mod",
    async buildPlan(args, ctx) {
        const name = args.name;
        const modsDir = await resolveModsDir(ctx);
        const modPath = join(modsDir, name);
        if (!existsSync(modPath))
            throw new Error(`mod_not_found: ${name}`);
        const backupFirst = args.backup_first ?? true;
        return {
            diff: `${backupFirst ? "Backup + " : ""}DELETE mod folder ${modPath} + remove from all profile modlists`,
            affectedFiles: [modPath],
            targets: [{ path: modPath, kind: "directory" }],
        };
    },
    async applyMutation(plan, ctx) {
        const name = plan.args.name;
        const backupFirst = plan.args.backup_first ?? true;
        const modsDir = await resolveModsDir(ctx);
        const modPath = join(modsDir, name);
        let backupName;
        let profilesUpdated = [];
        if (backupFirst) {
            backupName = await _nextBackupName(modsDir, name);
            await cp(modPath, join(modsDir, backupName), { recursive: true });
        }
        if (ctx.pipeClient) {
            const affectedProfiles = await _profilesReferencingMod(ctx.config.mo2Root, name);
            const resp = await ctx.pipeClient.call("mods.remove", { name });
            if (!resp.ok)
                throw new Error(resp.error?.message ?? "mods.remove failed");
            await invalidateWorld(ctx, affectedProfiles.length ? affectedProfiles : ["Default"]);
        }
        else {
            await rm(modPath, { recursive: true, force: true });
            profilesUpdated = await _scrubAllProfileModlists(ctx.config.mo2Root, name);
            await invalidateWorld(ctx, profilesUpdated.length ? profilesUpdated : ["Default"]);
        }
        return { removed: name, backup_name: backupName, profiles_updated: profilesUpdated };
    },
};
registerTool({
    name: "mo2_remove_mod",
    tier: "T3",
    description: "Remove a mod (physical delete + remove from all profile modlists). DEFAULT backup_first=true: creates <name>backupN before delete.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
