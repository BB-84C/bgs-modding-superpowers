/**
 * mo2_create_mod — T3 create an empty mod via live MO2 broker.
 *
 * This is live-only by design: empty mod creation must go through
 * IOrganizer.createMod/modList priority wiring rather than offline emulation.
 */
import { z } from "zod";
import { join } from "node:path";
import { mkdir } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir, resolveModsDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { invalidateWorld } from "./state-sync.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string().min(1),
        wins_over: z.string().min(1).optional(),
        profile: z.string().default("Default"),
    }).strict(),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }).strict(),
]);
const RESPONSE_META = {
    priority_convention: "mobase_full_space_higher_wins",
    modlist_file_order: "reverse_of_gui",
    gui_direction_hint: "priority_0_at_gui_top_loses; priority_(N-1)_at_gui_bottom_wins",
};
async function _targetPriority(mo2Root, profile, winsOver) {
    if (winsOver === undefined)
        return undefined;
    const p = await readProfile(join(mo2Root, "profiles", profile));
    const winsOverPri = p.mods.find((mod) => mod.name === winsOver)?.priority;
    if (winsOverPri == null)
        throw new Error(`wins_over_mod_not_found: ${winsOver}`);
    return winsOverPri + 1;
}
const handler = {
    toolName: "mo2_create_mod",
    async buildPlan(args, ctx) {
        const bound = requireBoundContext(ctx);
        if (!bound.pipeClient)
            throw new Error("live_mo2_required_for_create_mod");
        const profile = args.profile ?? "Default";
        // BUG-9 fix (2026-06-17): refuse plan generation when the requested
        // profile is not the live MO2's active profile. The applyMutation path
        // already enforces this; pushing it up to buildPlan prevents misleading
        // plan envelopes that look mintable but would never apply.
        await assertActiveProfile(ctx, profile);
        const winsOver = args.wins_over;
        const targetPri = await _targetPriority(bound.config.mo2Root, profile, winsOver);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const winsOverText = winsOver !== undefined
            ? ` (wins_over ${winsOver}, pri=${String(targetPri)})`
            : "";
        return {
            diff: `Create empty mod ${String(args.name)}${winsOverText}`,
            affectedFiles: [modlistPath],
            targets: [{ path: modlistPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        if (!bound.pipeClient)
            throw new Error("live_mo2_required_for_create_mod");
        const profile = plan.args.profile ?? "Default";
        await assertActiveProfile(ctx, profile);
        const winsOver = plan.args.wins_over;
        const targetPri = await _targetPriority(bound.config.mo2Root, profile, winsOver);
        const payload = { name: plan.args.name };
        if (targetPri !== undefined)
            payload.priority = targetPri;
        const resp = await bound.pipeClient.call("mods.create", payload);
        if (!resp.ok)
            throw new Error(resp.error?.message ?? "broker error");
        // Defensive: ensure mod folder exists on disk. broker mods.create may leave
        // the folder unmaterialized until MO2's next save cycle; downstream tools
        // (mo2_remove_mod buildPlan, etc.) check existsSync on the mod path and
        // would otherwise throw mod_not_found. Use the broker-returned
        // absolute_path when present; fall back to <modsDir>/<name>.
        const result = (resp.result ?? {});
        const modsDir = await resolveModsDir(ctx);
        const absPath = typeof result.absolute_path === "string"
            ? result.absolute_path
            : join(modsDir, plan.args.name);
        await mkdir(absPath, { recursive: true });
        await invalidateWorld(ctx, [profile]);
        return { ...result, _meta: RESPONSE_META };
    },
};
registerTool({
    name: "mo2_create_mod",
    tier: "T3",
    description: "Create empty mod via broker mods.create. Optional 'wins_over' positions it just above a named mod in precedence (= just below visually in MO2 GUI).",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
