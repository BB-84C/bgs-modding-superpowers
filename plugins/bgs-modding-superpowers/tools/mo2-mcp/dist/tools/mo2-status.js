/**
 * mo2_status — T1 read tool.
 *
 * Reports MO2 instance state: paths, game, profile, 7-signal detection result,
 * counts, MCP permission ceiling, sidecar + broker connection state.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { detectMo2Running } from "../detection.js";
import { readProfile } from "../profile-reader.js";
import { readMoIni } from "../mo-ini.js";
const inputSchema = z.object({ profile: z.string().optional() });
function nonEmpty(value) {
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
}
function resolveActiveProfile(args, ctx, ini) {
    return (nonEmpty(args.profile) ??
        nonEmpty(process.env.BGS_MO2_PROFILE) ??
        nonEmpty(ini.general.selectedProfile) ??
        nonEmpty(ctx.config.allowedProfiles[0]) ??
        null);
}
registerTool({
    name: "mo2_status",
    tier: "T1",
    description: "Report MO2 instance state: paths, game, active profile, MO2-running detection (3-tier ladder), mod/plugin counts, MCP permission ceiling, broker+sidecar connectivity.",
    inputSchema,
    handler: async (args, ctx) => {
        const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
        const profileName = resolveActiveProfile(args, ctx, ini);
        if (!profileName) {
            return {
                ok: false,
                result: null,
                error: {
                    code: "no_profile_available",
                    message: "No profile from args.profile, BGS_MO2_PROFILE, ModOrganizer.ini selected_profile, or allowed_profiles[0]",
                },
            };
        }
        const profileDir = join(ctx.config.mo2Root, "profiles", profileName);
        const detection = await detectMo2Running({
            mo2Root: ctx.config.mo2Root,
            profileDir,
        });
        let profile;
        try {
            profile = await readProfile(profileDir);
        }
        catch (e) {
            const message = e instanceof Error ? e.message : String(e);
            return {
                ok: false,
                result: null,
                error: { code: "profile_not_found", message: `${profileName}: ${message}` },
            };
        }
        return {
            ok: true,
            result: {
                mo2_root: ctx.config.mo2Root,
                game: ini.general.game,
                game_name: ini.general.gameName,
                game_path: ini.general.gamePath,
                profile: profile.name ?? profileName,
                permission_ceiling: ctx.config.permissionCeiling,
                deny_patterns: ctx.config.deny.length,
                detection: {
                    process_running: detection.processRunning,
                    shared_memory_present: detection.sharedMemoryPresent,
                    profile_lock_held: detection.profileLockHeld,
                    mo2_pid: detection.pid,
                    online: detection.online,
                },
                counts: {
                    mods_total: profile.mods.length,
                    mods_enabled: profile.mods.filter((m) => m.enabled).length,
                    plugins_total: profile.plugins.length,
                    plugins_enabled: profile.plugins.filter((p) => p.enabled).length,
                },
                broker_connected: !!ctx.pipeClient,
                sidecar_ready: !!ctx.sidecar,
            },
            error: null,
        };
    },
});
