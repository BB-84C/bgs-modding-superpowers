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
// BUG-10 fix (2026-06-17): mod name + plan_id + lease_token gain .min(1).
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string().min(1),
        above: z.string().optional(),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }),
]);
/**
 * Normalize the `above` arg: treat non-strings and empty strings as absent.
 *
 * BUG-20 fix (2026-06-17): OpenCode's tool-call surface can pass `above: ""`
 * when the user omits the field (some tool wrappers require an explicit string
 * for "optional"). The handler used to interpret that as a real mod-name
 * lookup, which always failed with `above_mod_not_found: ` (trailing space).
 * Per Lane 2B's `.min(1)` audit, `above` stays permissive at the Zod layer to
 * keep the wire schema agent-friendly; we normalize empty -> undefined here
 * inside the handler instead, so the tools/list inputSchema is unaffected and
 * the Anthropic-compat normalize path stays untouched.
 */
function _normalizeAbove(above) {
    if (typeof above !== "string")
        return undefined;
    if (above === "")
        return undefined;
    return above;
}
async function _targetPriority(mo2Root, profile, above) {
    if (above === undefined)
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
        const bound = requireBoundContext(ctx);
        if (!bound.pipeClient)
            throw new Error("live_mo2_required_for_create_mod");
        const profile = args.profile ?? "Default";
        // BUG-9 fix (2026-06-17): refuse plan generation when the requested
        // profile is not the live MO2's active profile. The applyMutation path
        // already enforces this; pushing it up to buildPlan prevents misleading
        // plan envelopes that look mintable but would never apply.
        await assertActiveProfile(ctx, profile);
        const above = _normalizeAbove(args.above);
        const targetPri = await _targetPriority(bound.config.mo2Root, profile, above);
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const aboveText = above !== undefined
            ? ` above ${above} (pri=${String(targetPri)})`
            : "";
        return {
            diff: `Create empty mod ${String(args.name)}${aboveText}`,
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
        const above = _normalizeAbove(plan.args.above);
        const targetPri = await _targetPriority(bound.config.mo2Root, profile, above);
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
        return result;
    },
};
registerTool({
    name: "mo2_create_mod",
    tier: "T3",
    description: "Create empty mod via broker mods.create. Optional 'above' positions it above a named mod.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
