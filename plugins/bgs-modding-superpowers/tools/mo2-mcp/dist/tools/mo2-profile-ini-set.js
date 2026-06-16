/**
 * mo2_profile_ini_set — T2 write profile-local game INI.
 *
 * Sets <profile>/<game>.ini / <game>Prefs.ini / <game>Custom.ini key.
 * Hard-rejects if MO2 holds profile files (would overwrite on profile save).
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { upsertIniValue } from "../ini-helpers.js";
import { readMoIni } from "../mo-ini.js";
import { detectMo2Running } from "../detection.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        profile: z.string().default("Default"),
        ini_name: z.enum(["game", "prefs", "custom"]),
        section: z.string(),
        key: z.string(),
        value: z.string(),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
async function _resolveIniPath(args, ctx) {
    const mo2Root = requireBoundContext(ctx).config.mo2Root;
    const ini = await readMoIni(join(mo2Root, "ModOrganizer.ini"));
    const game = ini.general.game ?? "fallout4";
    const fileMap = {
        game: `${game}.ini`,
        prefs: `${game}Prefs.ini`,
        custom: `${game}Custom.ini`,
    };
    return join(mo2Root, "profiles", args.profile, fileMap[args.ini_name]);
}
const handler = {
    toolName: "mo2_profile_ini_set",
    async buildPlan(args, ctx) {
        const bound = requireBoundContext(ctx);
        const profile = args.profile ?? "Default";
        const profileDir = join(bound.config.mo2Root, "profiles", profile);
        const det = await detectMo2Running({ mo2Root: bound.config.mo2Root, profileDir });
        if (det.profileLockHeld) {
            throw new Error("mo2_holds_profile_files: close MO2 first or use mo2_switch_profile");
        }
        const iniPath = await _resolveIniPath({ profile, ini_name: args.ini_name }, ctx);
        return {
            diff: `[${args.section}]\n${args.key}=${args.value}`,
            affectedFiles: [iniPath],
            targets: [{ path: iniPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const args = plan.args;
        const iniPath = await _resolveIniPath({
            profile: args.profile ?? "Default",
            ini_name: args.ini_name,
        }, ctx);
        let text = "";
        try {
            text = await readFile(iniPath, "utf8");
        }
        catch {
            // create
        }
        text = upsertIniValue(text, args.section, args.key, args.value);
        await atomicWriteText(iniPath, text);
        return { ini_path: iniPath, key_set: `${args.section}/${args.key}` };
    },
};
registerTool({
    name: "mo2_profile_ini_set",
    tier: "T2",
    description: "Set profile-local INI key. Refuses if MO2 holds profile files. Atomic temp+rename.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
