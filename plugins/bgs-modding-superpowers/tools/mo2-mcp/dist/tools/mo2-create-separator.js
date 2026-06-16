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
import { routeToPlanApply } from "../plan-apply.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { readMoIni } from "../mo-ini.js";
import { atomicWriteText } from "../atomic.js";
import { assertActiveProfile } from "../profile-guard.js";
import { invalidateWorld } from "./state-sync.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string(),
        above: z.string().optional(),
        color: z.string().optional(),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
function _separatorName(name) {
    return `${String(name)}_separator`;
}
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
    toolName: "mo2_create_separator",
    async buildPlan(args, ctx) {
        if (!ctx.pipeClient)
            throw new Error("live_mo2_required");
        const profile = args.profile ?? "Default";
        const targetPri = await _targetPriority(ctx.config.mo2Root, profile, args.above);
        const sepName = _separatorName(args.name);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const priText = targetPri === undefined ? "" : ` (pri=${targetPri})`;
        const colorText = typeof args.color === "string" ? ` color=${args.color}` : "";
        return {
            diff: `Create separator "${String(args.name)}" → ${sepName}${priText}${colorText}`,
            affectedFiles: [modlistPath],
            targets: [{ path: modlistPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        if (!ctx.pipeClient)
            throw new Error("live_mo2_required");
        const profile = plan.args.profile ?? "Default";
        await assertActiveProfile(ctx, profile);
        const sepName = _separatorName(plan.args.name);
        const targetPri = await _targetPriority(ctx.config.mo2Root, profile, plan.args.above);
        const payload = { name: sepName };
        if (targetPri !== undefined)
            payload.priority = targetPri;
        const resp = await ctx.pipeClient.call("mods.create", payload);
        if (!resp.ok)
            throw new Error(resp.error?.message ?? "broker error");
        // Defensive: ensure separator folder exists on disk (see mo2_create_mod for rationale).
        const result = (resp.result ?? {});
        const ini = await readMoIni(join(ctx.config.mo2Root, "ModOrganizer.ini"));
        const modsDir = ini.settings.modDirectory ?? join(ctx.config.mo2Root, "mods");
        const absPath = typeof result.absolute_path === "string"
            ? result.absolute_path
            : join(modsDir, sepName);
        await mkdir(absPath, { recursive: true });
        if (typeof plan.args.color === "string") {
            await atomicWriteText(join(absPath, "meta.ini"), `[General]\ncolor=${plan.args.color}\n`);
        }
        await invalidateWorld(ctx, [profile]);
        return { separator_name: sepName, color_set: typeof plan.args.color === "string" };
    },
};
registerTool({
    name: "mo2_create_separator",
    tier: "T3",
    description: "Create a separator (_separator suffix triggers FLAG_SEPARATOR). Optional color written to meta.ini.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
