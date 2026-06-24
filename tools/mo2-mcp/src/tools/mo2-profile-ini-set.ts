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
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { upsertIniValue } from "../ini-helpers.js";
import { readMoIni, resolveGameName } from "../mo-ini.js";
import { detectMo2Running } from "../detection.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): section + key + plan_id + lease_token gain .min(1).
// `value` stays a free-form string — clearing an INI key to empty is a
// legitimate use of upsertIniValue.
const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    profile: z.string().default("Default"),
    ini_name: z.enum(["game", "prefs", "custom"]),
    section: z.string().min(1),
    key: z.string().min(1),
    value: z.string(),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

async function _resolveIniPath(args: {
  profile: string;
  ini_name: "game" | "prefs" | "custom";
}, ctx: { binding: { requireBound: () => { config: { mo2Root: string } } } }): Promise<string> {
  const mo2Root = requireBoundContext(ctx).config.mo2Root;
  const ini = await readMoIni(join(mo2Root, "ModOrganizer.ini"));
  // Per-game INI filenames use the TitleCase display NAME, not the lowercase
  // internal key — e.g. "Starfield.ini", "StarfieldPrefs.ini" (NOT
  // "starfield.ini"). resolveGameName prefers `gameName=` from MO2's
  // `[General]` section and falls back to mapping `game=` (older MO2).
  const game = resolveGameName(ini.general);
  const fileMap = {
    game: `${game}.ini`,
    prefs: `${game}Prefs.ini`,
    custom: `${game}Custom.ini`,
  };
  return join(mo2Root, "profiles", args.profile, fileMap[args.ini_name]);
}

const handler: PlanApplyHandler = {
  toolName: "mo2_profile_ini_set",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    const profile = (args.profile as string) ?? "Default";
    const profileDir = join(bound.config.mo2Root, "profiles", profile);
    const det = await detectMo2Running({ mo2Root: bound.config.mo2Root, profileDir });
    if (det.profileLockHeld) {
      throw new Error(
        "mo2_holds_profile_files: close MO2 first or use mo2_switch_profile",
      );
    }
    const iniPath = await _resolveIniPath(
      { profile, ini_name: args.ini_name as "game" | "prefs" | "custom" },
      ctx,
    );
    return {
      diff: `[${args.section}]\n${args.key}=${args.value}`,
      affectedFiles: [iniPath],
      targets: [{ path: iniPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const args = plan.args;
    const iniPath = await _resolveIniPath(
      {
        profile: (args.profile as string) ?? "Default",
        ini_name: args.ini_name as "game" | "prefs" | "custom",
      },
      ctx,
    );
    let text = "";
    try {
      text = await readFile(iniPath, "utf8");
    } catch {
      // create
    }
    text = upsertIniValue(
      text,
      args.section as string,
      args.key as string,
      args.value as string,
    );
    await atomicWriteText(iniPath, text);
    return { ini_path: iniPath, key_set: `${args.section}/${args.key}` };
  },
};

registerTool({
  name: "mo2_profile_ini_set",
  tier: "T2",
  description:
    "Set profile-local INI key. Refuses if MO2 holds profile files. Atomic temp+rename.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
