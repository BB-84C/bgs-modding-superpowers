/**
 * mo2_rename_profile — T3 profile directory rename + selected_profile sync.
 *
 * MO2 must be closed because it owns profile directories and rewrites
 * ModOrganizer.ini on exit. The INI edit is line-local and preserves all other
 * bytes/lines as-is.
 */
import { z } from "zod";
import { existsSync } from "node:fs";
import { rename, readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { detectMo2Running } from "../detection.js";
import { readMoIni } from "../mo-ini.js";
import { atomicWriteText } from "../atomic.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): rename profile name args + plan_id/lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), old_name: z.string().min(1), new_name: z.string().min(1) }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

async function assertMo2Closed(mo2Root: string): Promise<void> {
  const det = await detectMo2Running({ mo2Root });
  if (det.processRunning) throw new Error("mo2_running: close MO2 before renaming profile");
}

function selectedProfileMatches(value: string | undefined, profileName: string): boolean {
  return value === profileName || value === `@ByteArray(${profileName})`;
}

function rewriteSelectedProfileLine(text: string, oldName: string, newName: string): { text: string; updated: boolean } {
  const newline = text.includes("\r\n") ? "\r\n" : "\n";
  const lines = text.split(/\r?\n/);
  let updated = false;
  const nextLines = lines.map((line) => {
    if (updated) return line;
    const match = line.match(/^(\s*selected_profile\s*=)(.*?)(\s*)$/);
    if (!match) return line;
    const current = match[2];
    if (!selectedProfileMatches(current, oldName)) return line;
    updated = true;
    const nextValue = current.startsWith("@ByteArray(") ? `@ByteArray(${newName})` : newName;
    return `${match[1]}${nextValue}${match[3]}`;
  });
  return { text: nextLines.join(newline), updated };
}

const handler: PlanApplyHandler = {
  toolName: "mo2_rename_profile",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    await assertMo2Closed(bound.config.mo2Root);
    const oldName = args.old_name as string;
    const newName = args.new_name as string;
    const profilesRoot = join(bound.config.mo2Root, "profiles");
    const oldDir = join(profilesRoot, oldName);
    const newDir = join(profilesRoot, newName);
    if (!existsSync(oldDir)) throw new Error("profile_not_found");
    if (existsSync(newDir)) throw new Error("target_exists");
    const iniPath = join(bound.config.mo2Root, "ModOrganizer.ini");
    const ini = await readMoIni(iniPath);
    const needsIniUpdate = selectedProfileMatches(ini.general.selectedProfile, oldName);
    return {
      diff: `Rename profile dir + ${needsIniUpdate ? "update ModOrganizer.ini selected_profile" : "no ini update"}`,
      affectedFiles: [newDir, ...(needsIniUpdate ? [iniPath] : [])],
      targets: needsIniUpdate ? [{ path: iniPath, kind: "text-file" }] : [],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    const oldName = plan.args.old_name as string;
    const newName = plan.args.new_name as string;
    const profilesRoot = join(bound.config.mo2Root, "profiles");
    await rename(join(profilesRoot, oldName), join(profilesRoot, newName));

    const iniPath = join(bound.config.mo2Root, "ModOrganizer.ini");
    const text = await readFile(iniPath, "utf8");
    const rewritten = rewriteSelectedProfileLine(text, oldName, newName);
    if (rewritten.updated) {
      await atomicWriteText(iniPath, rewritten.text);
      return { renamed: true, ini_updated: true };
    }
    return { renamed: true, ini_updated: false };
  },
};

registerTool({
  name: "mo2_rename_profile",
  tier: "T3",
  description:
    "Rename a profile (MO2 must be closed). Updates ModOrganizer.ini selected_profile if it matched old name.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
