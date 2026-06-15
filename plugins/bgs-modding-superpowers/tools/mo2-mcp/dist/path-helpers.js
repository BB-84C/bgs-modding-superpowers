/**
 * Path helpers — derive common paths from ToolContext.
 *
 * Per PLAN-PATCH P-F1: extracted as shared so all S4/S5 tools reuse.
 */
import { join } from "node:path";
import { readMoIni } from "./mo-ini.js";
export async function resolveModMetaPath(modName, ctx) {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
    return join(modsDir, modName, "meta.ini");
}
export async function resolveModsDir(ctx) {
    const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
    return ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
}
export function resolveProfileDir(ctx, profile) {
    return join(ctx.config.mo2Root, "profiles", profile ?? ctx.config.allowedProfiles[0]);
}
