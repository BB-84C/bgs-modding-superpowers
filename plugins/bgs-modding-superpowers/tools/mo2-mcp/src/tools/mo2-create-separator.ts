/**
 * mo2_create_separator — T3 create an MO2 separator mod.
 *
 * MO2 flags separators by conventional `<name>_separator` mod names. Color has
 * no public mobase setter, so the MCP writes meta.ini directly and refreshes.
 */
import { z } from "zod";
import { join } from "node:path";
import { mkdir } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply, type PlanApplyHandler } from "../plan-apply.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { readMoIni } from "../mo-ini.js";
import { atomicWriteText } from "../atomic.js";
import { assertActiveProfile } from "../profile-guard.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext } from "../binding.js";

const inputSchema = z.discriminatedUnion("mode", [
  z.object({
    mode: z.literal("plan"),
    name: z.string().min(1),
    wins_over: z.string().min(1).optional(),
    color: z.string().optional(),
    profile: z.string().default("Default"),
  }).strict(),
  z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }).strict(),
]);

const RESPONSE_META = {
  priority_convention: "mobase_full_space_higher_wins",
  modlist_file_order: "reverse_of_gui",
  gui_direction_hint: "priority_0_at_gui_top_loses; priority_(N-1)_at_gui_bottom_wins",
};

function _separatorName(name: unknown): string {
  return `${String(name)}_separator`;
}

async function _targetPriority(
  mo2Root: string,
  profile: string,
  winsOver: string | undefined,
): Promise<number | undefined> {
  if (winsOver === undefined) return undefined;
  const p = await readProfile(join(mo2Root, "profiles", profile));
  const winsOverPri = p.mods.find((mod) => mod.name === winsOver)?.priority;
  if (winsOverPri == null) throw new Error(`wins_over_mod_not_found: ${winsOver}`);
  return winsOverPri + 1;
}

const handler: PlanApplyHandler = {
  toolName: "mo2_create_separator",
  async buildPlan(args, ctx) {
    const bound = requireBoundContext(ctx);
    if (!bound.pipeClient) throw new Error("live_mo2_required");
    const profile = (args.profile as string | undefined) ?? "Default";
    // BUG-9 fix (2026-06-17): refuse plan generation when the requested
    // profile is not the live MO2's active profile; mirrors the
    // applyMutation guard.
    await assertActiveProfile(ctx, profile);
    const winsOver = args.wins_over as string | undefined;
    const targetPri = await _targetPriority(bound.config.mo2Root, profile, winsOver);
    const sepName = _separatorName(args.name);
    const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
    const winsOverText = winsOver === undefined ? "" : ` (wins_over ${winsOver}, pri=${targetPri})`;
    const colorText = typeof args.color === "string" ? ` color=${args.color}` : "";
    return {
      diff: `Create separator "${String(args.name)}" → ${sepName}${winsOverText}${colorText}`,
      affectedFiles: [modlistPath],
      targets: [{ path: modlistPath, kind: "text-file" }],
    };
  },
  async applyMutation(plan, ctx) {
    const bound = requireBoundContext(ctx);
    if (!bound.pipeClient) throw new Error("live_mo2_required");
    const profile = (plan.args.profile as string | undefined) ?? "Default";
    await assertActiveProfile(ctx, profile);
    const sepName = _separatorName(plan.args.name);
    const winsOver = plan.args.wins_over as string | undefined;
    const targetPri = await _targetPriority(bound.config.mo2Root, profile, winsOver);
    const payload: { name: string; priority?: number } = { name: sepName };
    if (targetPri !== undefined) payload.priority = targetPri;

    const resp = await bound.pipeClient.call("mods.create", payload);
    if (!resp.ok) throw new Error(resp.error?.message ?? "broker error");

    // Defensive: ensure separator folder exists on disk (see mo2_create_mod for rationale).
    const result = (resp.result ?? {}) as Record<string, unknown>;
    const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
    const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
    const absPath = typeof result.absolute_path === "string"
      ? (result.absolute_path as string)
      : join(modsDir, sepName);
    await mkdir(absPath, { recursive: true });

    if (typeof plan.args.color === "string") {
      await atomicWriteText(join(absPath, "meta.ini"), `[General]\ncolor=${plan.args.color}\n`);
    }

    await invalidateWorld(ctx, [profile]);

    return { separator_name: sepName, color_set: typeof plan.args.color === "string", _meta: RESPONSE_META };
  },
};

registerTool({
  name: "mo2_create_separator",
  tier: "T3",
  description:
    "Create a separator (_separator suffix triggers FLAG_SEPARATOR). Optional 'wins_over' positions it just above a named mod in precedence (= just below visually in MO2 GUI). Optional color written to meta.ini.",
  inputSchema,
  handler: (args, ctx) =>
    routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots) as Promise<unknown>,
});
