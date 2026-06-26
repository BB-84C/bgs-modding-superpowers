/**
 * mo2_send_mod_to — T3 reposition a mod by named mode.
 *
 * Modes (per oracle §A3):
 *   - top: highest priority (numerically priority-count-1)
 *   - bottom: lowest priority (priority 0)
 *   - priority: explicit integer
 *   - above_separator: place above named separator (separator priority + 1 in FULL priority space)
 *   - above_first_conflict: place above highest-priority mod that shares files (sidecar)
 *   - below_last_conflict: place below lowest-priority mod that shares files (sidecar)
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import type { ToolContext } from "../types.js";
import { requireBoundContext, bindingSnapshot } from "../binding.js";

const ModeSchema = z.enum([
  "top",
  "bottom",
  "priority",
  "above_separator",
  "above_first_conflict",
  "below_last_conflict",
]);

// BUG-10 fix (2026-06-17): mod name + plan_id + lease_token gain .min(1).
// target_separator stays optional (only used in above_separator mode).
const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string().min(1),
    target_mode: ModeSchema,
    target_priority: z.number().int().optional(),
    target_separator: z.string().optional(),
    profile: z.string().default("Default"),
  }),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);

async function _computeTargetPriority(
  args: Record<string, unknown>,
  ctx: ToolContext,
  profile: string,
): Promise<number> {
  const bound = requireBoundContext(ctx);
  const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
  // FULL priority space (separators occupy slots). mobase IModList.setPriority
  // accepts priorities in this space — valid range [0, mods.length - 1]. The
  // 2026-06-17 BUG-B fix (issue #14) introduced nonSepRank conversion based on
  // a wrong conclusion about broker semantics; that fix is reverted here.
  // See docs/issues/BUG-mo2-mcp-send_mod_to-semantics-2026-06-27.md.
  const maxPri = Math.max(0, p.mods.length - 1);
  const clamp = (v: number): number => Math.max(0, Math.min(v, maxPri));
  const mode = args.target_mode as string;

  switch (mode) {
    case "top":
      // Highest priority = bottom of MO2 GUI = top of modlist.txt = wins
      return maxPri;
    case "bottom":
      // Priority 0 = top of MO2 GUI = bottom of modlist.txt = loses
      return 0;
    case "priority":
      return clamp((args.target_priority as number) ?? 0);
    case "above_separator": {
      const sep = p.mods.find((m) => m.isSeparator && m.name === args.target_separator);
      if (!sep) throw new Error(`separator_not_found: ${args.target_separator}`);
      // "Above" the separator visually = higher priority numerically (closer to
      // bottom of MO2 GUI). Place mod at sep.priority + 1; clamp guards against
      // separators at the very top.
      return clamp(sep.priority + 1);
    }
    case "above_first_conflict":
    case "below_last_conflict": {
      const sidecar = bound.sidecar;
      if (!sidecar) {
        throw new Error("sidecar_required_for_conflict_mode");
      }
      const conflicts = (await sidecar.call("assets.conflicts", {
        profile_dir: join(bound.config.mo2Root, "profiles", profile),
        max_results: 5000,
      })) as { conflicts?: Array<{ providers?: string[] }> };
      const conflictMods = (conflicts.conflicts ?? [])
        .filter((c) => c.providers?.includes(args.name as string))
        .flatMap((c) => (c.providers ?? []).filter((n) => n !== args.name));
      if (conflictMods.length === 0) {
        throw new Error("no_conflicts_found");
      }
      // Use FULL priorities directly, no nonSepRank conversion.
      const conflictPris = conflictMods
        .map((n) => p.mods.find((m) => m.name === n))
        .filter((m): m is (typeof p.mods)[number] => m !== undefined && !m.isSeparator)
        .map((m) => m.priority);
      if (conflictPris.length === 0) {
        throw new Error("no_conflicts_found");
      }
      if (mode === "above_first_conflict") return clamp(Math.max(...conflictPris) + 1);
      return clamp(Math.min(...conflictPris) - 1);
    }
    default:
      throw new Error(`unknown_mode: ${mode}`);
  }
}

const handler: PlanApplyHandler = {
  toolName: "mo2_send_mod_to",
  async buildPlan(args, ctx) {
    const profile = (args.profile as string) ?? "Default";
    // BUG-9 fix (2026-06-17): refuse plan generation when MO2 is live on a
    // different profile (mirrors the apply-time check). Priority reorder
    // targets the requested profile's modlist.txt; planning against the
    // wrong profile produces a diff that does not match what apply would
    // later try to enforce.
    await assertActiveProfile(ctx, profile);
    const targetPri = await _computeTargetPriority(args, ctx, profile);
    const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
    return {
      diff: `${args.name}: → priority ${targetPri} (mode=${args.target_mode})`,
      affectedFiles: [modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    const args = plan.args;
    const profile = (args.profile as string) ?? "Default";

    if (bound.pipeClient) {
      await assertActiveProfile(ctx, profile);
      const targetPri = await _computeTargetPriority(args, ctx, profile);
      const resp = await bound.pipeClient.call("mods.set_priority", {
        name: args.name,
        priority: targetPri,
      });
      if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");
      return {
        ...(resp.result as Record<string, unknown>),
        target_mode: args.target_mode,
      };
    }
    // Offline: rewrite modlist.txt line order
    const targetPri = await _computeTargetPriority(args, ctx, profile);
    const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
    const text = await readFile(modlistPath, "utf8");
    const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
    const idx = lines.findIndex((l) => l.replace(/^[+\-]/, "") === args.name);
    if (idx < 0) throw new Error("mod_not_found_in_modlist");
    const [moved] = lines.splice(idx, 1);
    // priority N-1 = top of mobase = bottom of modlist.txt; convert
    const insertIdx = Math.max(0, Math.min(lines.length - targetPri, lines.length));
    lines.splice(insertIdx, 0, moved);
    await atomicWriteText(modlistPath, lines.join("\n") + "\n");
    return {
      name: args.name,
      new_priority: targetPri,
      target_mode: args.target_mode,
      source: "offline_modlist_reorder",
    };
  },
};

registerTool({
  name: "mo2_send_mod_to",
  tier: "T3",
  description:
    "Reposition a mod by mode: top/bottom/priority/above_separator/above_first_conflict/below_last_conflict.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
