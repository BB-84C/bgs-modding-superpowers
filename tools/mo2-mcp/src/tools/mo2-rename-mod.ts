/**
 * mo2_rename_mod — T3 rename a mod across all profile modlists.
 *
 * Live path delegates to broker mods.rename (which wraps mobase renameMod and
 * synchronizes profiles). Offline path mirrors that behavior by renaming the
 * mod directory and rewriting every profile's modlist.txt line that references
 * the old name.
 */
import { z } from "zod";
import { readdir, readFile, rename } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { readMoIni } from "../mo-ini.js";
import { atomicWriteText } from "../atomic.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

// BUG-10 fix (2026-06-17): rename name args + plan_id/lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), old_name: z.string().min(1), new_name: z.string().min(1) }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

function _lineReferencesMod(line: string, modName: string): boolean {
  const match = line.match(/^([+\-])(.+)$/);
  return match?.[2] === modName;
}

async function _resolveModsDir(mo2Root: string): Promise<string> {
  const ini = await readMoIni(join(mo2Root, "ModOrganizer.ini"));
  return ini.settings.modDirectory ?? join(mo2Root, "mods");
}

async function _affectedModlists(mo2Root: string, oldName: string): Promise<Array<{ profile: string; path: string }>> {
  const profilesRoot = join(mo2Root, "profiles");
  const profiles = await readdir(profilesRoot).catch(() => [] as string[]);
  const affected: Array<{ profile: string; path: string }> = [];
  for (const profile of profiles) {
    const modlistPath = join(profilesRoot, profile, "modlist.txt");
    try {
      const text = await readFile(modlistPath, "utf8");
      if (text.split(/\r?\n/).some((line) => _lineReferencesMod(line, oldName))) {
        affected.push({ profile, path: modlistPath });
      }
    } catch {
      // Skip non-profile dirs or unreadable modlists.
    }
  }
  return affected;
}

function _rewriteModlist(text: string, oldName: string, newName: string): string {
  return text
    .split(/\r?\n/)
    .map((line) => {
      const match = line.match(/^([+\-])(.+)$/);
      if (match?.[2] === oldName) return `${match[1]}${newName}`;
      return line;
    })
    .join("\n");
}

const handler: PlanApplyHandler = {
  toolName: "mo2_rename_mod",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    const oldName = args.old_name as string;
    const newName = args.new_name as string;
    const affected = await _affectedModlists(bound.config.mo2Root, oldName);
    const modsDir = await _resolveModsDir(bound.config.mo2Root);
    const modDir = join(modsDir, oldName);
    return {
      diff: `Rename ${oldName} → ${newName} across ${affected.length} profiles + mod dir`,
      affectedFiles: affected.map((entry) => entry.path),
      targets: [
        ...affected.map((entry) => ({ path: entry.path, kind: "text-file" as const })),
        { path: modDir, kind: "directory" as const },
      ],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    // Live and offline paths share the same fs-level work: rename the mod
    // directory and rewrite every profile's modlist.txt. We previously routed
    // live mode through broker mods.rename, but that required organizer.refresh
    // beforehand (to make MO2 see fs-created mods) which destabilized MO2's
    // internal model. The broker round-trip provided no semantic value beyond
    // the fs work we do here, so the live path was collapsed to call the same
    // fs logic + invalidate the sidecar World cache.
    const oldName = plan.args.old_name as string;
    const newName = plan.args.new_name as string;

    const modsDir = await _resolveModsDir(bound.config.mo2Root);
    await rename(join(modsDir, oldName), join(modsDir, newName));

    const profilesRoot = join(bound.config.mo2Root, "profiles");
    const profiles = await readdir(profilesRoot).catch(() => [] as string[]);
    const updated: string[] = [];
    for (const profile of profiles) {
      const modlistPath = join(profilesRoot, profile, "modlist.txt");
      try {
        const text = await readFile(modlistPath, "utf8");
        const newText = _rewriteModlist(text, oldName, newName);
        if (newText !== text) {
          await atomicWriteText(modlistPath, newText);
          updated.push(profile);
        }
      } catch {
        // Skip non-profile dirs or unreadable modlists.
      }
    }

    if (bound.pipeClient) {
      await invalidateWorld(ctx, updated.length ? updated : ["Default"]);
    }
    return { renamed_dir: true, profiles_updated: updated };
  },
};

registerTool({
  name: "mo2_rename_mod",
  tier: "T3",
  description:
    "Rename mod across ALL profiles + mod folder. Live: broker mods.rename. Offline: fs rename + per-profile modlist.txt rewrite.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
