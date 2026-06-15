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
const inputSchema = z.object({});
registerTool({
    name: "mo2_status",
    tier: "T1",
    description: "Report MO2 instance state: paths, game, active profile, MO2-running detection (3-tier ladder), mod/plugin counts, MCP permission ceiling, broker+sidecar connectivity.",
    inputSchema,
    handler: async (_args, ctx) => {
        const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
        const profileName = ctx.config.allowedProfiles[0];
        const profileDir = join(ctx.config.mo2Root, "profiles", profileName);
        const detection = await detectMo2Running({
            mo2Root: ctx.config.mo2Root,
            profileDir,
        });
        let profile = null;
        try {
            profile = await readProfile(profileDir);
        }
        catch {
            // profile dir may be missing in tests
        }
        return {
            ok: true,
            result: {
                mo2_root: ctx.config.mo2Root,
                game: ini.general.game,
                game_name: ini.general.gameName,
                game_path: ini.general.gamePath,
                profile: profile?.name ?? profileName,
                permission_ceiling: ctx.config.permissionCeiling,
                deny_patterns: ctx.config.deny.length,
                detection: {
                    process_running: detection.processRunning,
                    shared_memory_present: detection.sharedMemoryPresent,
                    profile_lock_held: detection.profileLockHeld,
                    mo2_pid: detection.pid,
                    online: detection.online,
                },
                counts: profile
                    ? {
                        mods_total: profile.mods.length,
                        mods_enabled: profile.mods.filter((m) => m.enabled).length,
                        plugins_total: profile.plugins.length,
                        plugins_enabled: profile.plugins.filter((p) => p.enabled).length,
                    }
                    : null,
                broker_connected: !!ctx.pipeClient,
                sidecar_ready: !!ctx.sidecar,
            },
            error: null,
        };
    },
});
