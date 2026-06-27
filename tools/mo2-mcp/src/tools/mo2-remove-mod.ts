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
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { resolveModsDir } from "../path-helpers.js";
import { atomicWriteText } from "../atomic.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";
import {
  CONFLICT_PREVIEW_SIDECAR_SKIPPED,
  computeRemovedPreview,
  isSidecarReport,
  previewOrUnavailable,
  reportForMod,
} from "../conflict-preview.js";
import { logApplyEvent } from "../log-apply.js";

const inputSchema = z.discriminatedUnion("mode", [
  z.object({ mode: z.literal("plan"), name: z.string(), backup_first: z.boolean().default(true) }),
  z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);

function _lineReferencesMod(line: string, modName: string): boolean {
  return line.replace(/^[+\-]/, "") === modName;
}

async function _nextBackupName(modsDir: string, name: string): Promise<string> {
  let i = 0;
  while (existsSync(join(modsDir, `${name}backup${i}`))) i++;
  return `${name}backup${i}`;
}

async function _scrubAllProfileModlists(mo2Root: string, name: string): Promise<string[]> {
  const profilesRoot = join(mo2Root, "profiles");
  const profiles = await readdir(profilesRoot).catch(() => [] as string[]);
  const updated: string[] = [];
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
    } catch {
      // Skip non-profile dirs or unreadable modlists.
    }
  }
  return updated;
}

async function _profilesReferencingMod(mo2Root: string, name: string): Promise<string[]> {
  const profilesRoot = join(mo2Root, "profiles");
  const profiles = await readdir(profilesRoot).catch(() => [] as string[]);
  const referenced: string[] = [];
  for (const profile of profiles) {
    const modlistPath = join(profilesRoot, profile, "modlist.txt");
    try {
      const text = await readFile(modlistPath, "utf8");
      if (text.split(/\r?\n/).some((line) => _lineReferencesMod(line, name))) {
        referenced.push(profile);
      }
    } catch {
      // Skip non-profile dirs or unreadable modlists.
    }
  }
  return referenced.sort();
}

const handler: PlanApplyHandler = {
  toolName: "mo2_remove_mod",
  async buildPlan(args, ctx) {
    const name = args.name as string;
    const modsDir = await resolveModsDir(ctx);
    const modPath = join(modsDir, name);
    if (!existsSync(modPath)) throw new Error(`mod_not_found: ${name}`);
    const backupFirst = (args.backup_first as boolean | undefined) ?? true;
    return {
      diff: `${backupFirst ? "Backup + " : ""}DELETE mod folder ${modPath} + remove from all profile modlists`,
      affectedFiles: [modPath],
      targets: [{ path: modPath, kind: "directory" }],
    };
  },
  async applyMutation(plan, ctx) {
    const name = plan.args.name as string;
    const backupFirst = (plan.args.backup_first as boolean | undefined) ?? true;
    const modsDir = await resolveModsDir(ctx);
    const modPath = join(modsDir, name);
    let backupName: string | undefined;
    const bound = requireBoundContext(ctx);
    const profile = bound.config.allowedProfiles[0] ?? "Default";
    const preReport = bound.sidecar
      ? await previewOrUnavailable(() => reportForMod(name, bound, profile))
      : undefined;

    if (backupFirst) {
      backupName = await _nextBackupName(modsDir, name);
      await cp(modPath, join(modsDir, backupName), { recursive: true });
    }

    // BUG-15 fix (2026-06-17) - preface. The broker call below is
    // informational for the unified filesystem cleanup that follows: it
    // tells MO2's in-memory model to drop the mod, but it does NOT reliably
    // flush profiles/<*>/modlist.txt. The previous code branched on
    // backup_first via the broker error path: backup_first=true happened
    // to take the "not_found + folder exists" fallback that already called
    // _scrubAllProfileModlists, while backup_first=false hit the broker-ok
    // branch and skipped the scrub, leaving orphan rows on disk.
    if (bound.pipeClient) {
      const resp = await bound.pipeClient.call("mods.remove", { name }) as {
        ok: boolean;
        result?: Record<string, unknown>;
        error?: { message?: string } | null;
      };
      if (!resp.ok) {
        const isNotFound = /mod ['"]?.+['"]? not found/i.test(resp.error?.message ?? "");
        if (!isNotFound || !existsSync(modPath)) {
          throw new Error(resp.error?.message ?? "mods.remove failed");
        }
        // not_found + folder exists: broker's model lagged behind disk
        // (e.g. fs-created mod, or cp-driven refresh races). Fall through
        // into the unified filesystem cleanup so the orphan row also gets
        // removed.
      }
    }

    // BUG-15 fix (2026-06-17) - unified removal. Physical rm + profile
    // modlist scrub run on all three paths (broker-ok, broker-not_found,
    // offline). This single seam guarantees profiles/<*>/modlist.txt no
    // longer references the removed mod regardless of which path we
    // entered. `rm` with force=true is a no-op when the folder is already
    // gone (broker may have deleted it). The scrub touches every profile
    // that referenced the mod and returns the changed set.
    if (existsSync(modPath)) {
      await rm(modPath, { recursive: true, force: true });
    }
    const profilesUpdated = await _scrubAllProfileModlists(bound.config.mo2Root, name);
    await invalidateWorld(ctx, profilesUpdated.length ? profilesUpdated : ["Default"]);
    await logApplyEvent(
      handler.toolName,
      `removed "${name}" backup="${backupName ?? "none"}"`,
      bound,
      plan.planId,
      profile,
    );
    const conflictsPreview = bound.sidecar
      ? isSidecarReport(preReport)
        ? computeRemovedPreview(preReport)
        : preReport
      : CONFLICT_PREVIEW_SIDECAR_SKIPPED;

    return { removed: name, backup_name: backupName, profiles_updated: profilesUpdated, conflicts_preview: conflictsPreview };
  },
};

registerTool({
  name: "mo2_remove_mod",
  tier: "T3",
  description:
    "Remove a mod (physical delete + remove from all profile modlists). DEFAULT backup_first=true: creates <name>backupN before delete.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
