/**
 * mo2_create_mod — T3 create an empty mod via live MO2 broker.
 *
 * This is live-only by design: empty mod creation must go through
 * IOrganizer.createMod/modList priority wiring rather than offline emulation.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { refreshOrganizerAndInvalidateWorld } from "./state-sync.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string(),
        above: z.string().optional(),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
async function _targetPriority(mo2Root, profile, above) {
    if (typeof above !== "string")
        return undefined;
    const p = await readProfile(join(mo2Root, "profiles", profile));
    const abovePri = p.mods.find((mod) => mod.name === above)?.priority;
    if (abovePri == null)
        throw new Error(`above_mod_not_found: ${above}`);
    return abovePri + 1;
}
const handler = {
    toolName: "mo2_create_mod",
    async buildPlan(args, ctx) {
        if (!ctx.pipeClient)
            throw new Error("live_mo2_required_for_create_mod");
        const profile = args.profile ?? "Default";
        const targetPri = await _targetPriority(ctx.config.mo2Root, profile, args.above);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const aboveText = typeof args.above === "string"
            ? ` above ${args.above} (pri=${String(targetPri)})`
            : "";
        return {
            diff: `Create empty mod ${String(args.name)}${aboveText}`,
            affectedFiles: [modlistPath],
            targets: [{ path: modlistPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        if (!ctx.pipeClient)
            throw new Error("live_mo2_required_for_create_mod");
        const profile = plan.args.profile ?? "Default";
        await assertActiveProfile(ctx, profile);
        const targetPri = await _targetPriority(ctx.config.mo2Root, profile, plan.args.above);
        const payload = { name: plan.args.name };
        if (targetPri !== undefined)
            payload.priority = targetPri;
        const resp = await ctx.pipeClient.call("mods.create", payload);
        if (!resp.ok)
            throw new Error(resp.error?.message ?? "broker error");
        await refreshOrganizerAndInvalidateWorld(ctx, [profile]);
        return resp.result;
    },
};
registerTool({
    name: "mo2_create_mod",
    tier: "T3",
    description: "Create empty mod via broker mods.create. Optional 'above' positions it above a named mod.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
