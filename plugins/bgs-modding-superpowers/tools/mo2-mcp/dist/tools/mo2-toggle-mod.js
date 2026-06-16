/**
 * mo2_toggle_mod — T3 enable/disable mod.
 *
 * Live: broker mods.set_active.
 * Offline: modlist.txt atomic rewrite (find line ending with mod name, swap +/-).
 *
 * Lease is on modlist.txt content hash (T3 + plan/apply mandatory).
 */
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { readProfile } from "../profile-reader.js";
import { resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string(),
        enabled: z.boolean(),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
const handler = {
    toolName: "mo2_toggle_mod",
    async buildPlan(args, ctx) {
        const profile = args.profile ?? "Default";
        const profileDir = resolveProfileDir(ctx, profile);
        const modlistPath = join(profileDir, "modlist.txt");
        const p = await readProfile(profileDir);
        const mod = p.mods.find((m) => m.name === args.name);
        if (!mod) {
            throw new Error(`mod_not_found: ${args.name}`);
        }
        if (mod.enabled === args.enabled) {
            return {
                diff: `no-op (${args.name} already ${args.enabled ? "enabled" : "disabled"})`,
                affectedFiles: [modlistPath],
                targets: [{ path: modlistPath, kind: "text-file" }],
            };
        }
        return {
            diff: `${args.name}: ${mod.enabled ? "+" : "-"} → ${args.enabled ? "+" : "-"}`,
            affectedFiles: [modlistPath],
            targets: [{ path: modlistPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const profile = args.profile ?? "Default";
        if (bound.pipeClient) {
            await assertActiveProfile(ctx, profile);
            const resp = await bound.pipeClient.call("mods.set_active", {
                names: [args.name],
                active: args.enabled,
            });
            if (!resp.ok)
                throw new Error(resp.error?.message ?? "broker error");
            return resp.result;
        }
        const modlistPath = join(resolveProfileDir(ctx, profile), "modlist.txt");
        const text = await readFile(modlistPath, "utf8");
        const lines = text.split(/\r?\n/);
        const newLines = lines.map((l) => {
            if (!l)
                return l;
            const bare = l.replace(/^[+\-]/, "");
            if (bare === args.name && !bare.endsWith("_separator")) {
                return (args.enabled ? "+" : "-") + args.name;
            }
            return l;
        });
        await atomicWriteText(modlistPath, newLines.join("\n"));
        return {
            name: args.name,
            enabled: args.enabled,
            source: "offline_modlist_rewrite",
        };
    },
};
registerTool({
    name: "mo2_toggle_mod",
    tier: "T3",
    description: "Enable or disable a mod. Plan/apply with lease on modlist.txt content hash. Live: broker pipe; offline: atomic file rewrite.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
