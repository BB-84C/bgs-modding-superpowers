/**
 * Path helpers — derive common paths from ToolContext.
 *
 * Per PLAN-PATCH P-F1: extracted as shared so all S4/S5 tools reuse.
 */
import { join } from "node:path";
import { readMoIni } from "./mo-ini.js";
import { requireBoundContext } from "./binding.js";
import type { ToolContext } from "./types.js";

export async function resolveModMetaPath(modName: string, ctx: ToolContext): Promise<string> {
  const bound = requireBoundContext(ctx);
  const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
  const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
  return join(modsDir, modName, "meta.ini");
}

export async function resolveModsDir(ctx: ToolContext): Promise<string> {
  const bound = requireBoundContext(ctx);
  const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
  return ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
}

export function resolveProfileDir(ctx: ToolContext, profile?: string): string {
  const bound = requireBoundContext(ctx);
  return join(bound.config.mo2Root, "profiles", profile ?? bound.config.allowedProfiles[0]);
}
