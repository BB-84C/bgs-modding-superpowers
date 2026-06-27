/**
 * mo2_toggle_plugin — T3 enable/disable plugin.
 *
 * Live: broker plugins.set_state.
 * Offline: plugins.txt rewrite (* prefix = enabled per FO4/SSE convention).
 *
 * Optional also_hide_file=true: renames mods/<owner>/Data/<plugin>.esp ↔ .mohidden
 * for "Optional ESP" semantics (USVFS skipFileSuffixes). Requires live MO2 to
 * resolve owning mod via organizer.get_file_origins.
 */
import { z } from "zod";
import { readFile, rename } from "node:fs/promises";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { routeToPlanApply } from "../plan-apply.js";
import { atomicWriteText } from "../atomic.js";
import { resolveModsDir, resolveProfileDir } from "../path-helpers.js";
import { assertActiveProfile } from "../profile-guard.js";
import { requireBoundContext } from "../binding.js";
import { pollPluginWarnings } from "../plugin-warnings.js";
import { logApplyEvent } from "../log-apply.js";
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string(),
        enabled: z.boolean(),
        also_hide_file: z.boolean().default(false),
        profile: z.string().default("Default"),
    }),
    z.object({ mode: z.literal("apply"), plan_id: z.string(), lease_token: z.string() }),
]);
const handler = {
    toolName: "mo2_toggle_plugin",
    async buildPlan(args, ctx) {
        const profile = args.profile ?? "Default";
        // BUG-9 fix (2026-06-17): same cross-profile guard as mo2_toggle_mod
        // buildPlan. Without this, a plan can be minted against
        // profiles/<other>/plugins.txt while the live broker owns plugins.txt
        // for the active profile.
        await assertActiveProfile(ctx, profile);
        const pluginsPath = join(resolveProfileDir(ctx, profile), "plugins.txt");
        const targets = [
            { path: pluginsPath, kind: "text-file" },
        ];
        const affected = [pluginsPath];
        const bound = requireBoundContext(ctx);
        if (args.also_hide_file) {
            if (!bound.pipeClient) {
                throw new Error("also_hide_file_requires_live_mo2: pipe needed to find owning mod via organizer.get_file_origins");
            }
            const origin = await bound.pipeClient.call("organizer.get_file_origins", {
                filename: args.name,
            });
            const owners = origin.result?.origins ?? [];
            const ownerMod = owners[0];
            if (!ownerMod || ownerMod === "data") {
                throw new Error(`plugin_not_owned_by_mod: ${args.name}`);
            }
            const modsDir = await resolveModsDir(ctx);
            const espPath = join(modsDir, ownerMod, args.name);
            affected.push(espPath);
            targets.push({ path: espPath, kind: "text-file" });
        }
        return {
            diff: `plugins.txt: ${args.enabled ? "*" : ""}${args.name}${args.also_hide_file ? ` + file ${args.enabled ? "unhide" : "→ .mohidden"}` : ""}`,
            affectedFiles: affected,
            targets,
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const profile = args.profile ?? "Default";
        const pluginsPath = join(resolveProfileDir(ctx, profile), "plugins.txt");
        let brokerResult;
        if (bound.pipeClient) {
            await assertActiveProfile(ctx, profile);
            // PluginState::Active=2, Inactive=1 in mobase
            const stateInt = args.enabled ? 2 : 1;
            const resp = await bound.pipeClient.call("plugins.set_state", {
                name: args.name,
                state: stateInt,
            });
            if (!resp.ok)
                throw new Error(resp.error?.message ?? "broker error");
            brokerResult = resp.result;
        }
        // BUG-14 fix (2026-06-17): broker plugins.set_state mutates the
        // IPluginList in-memory state but does NOT invoke
        // Profile::writePluginsList; MO2 only flushes plugins.txt on shutdown /
        // profile change / explicit save. The MCP contract is that an "ok"
        // apply produces visible disk state, so we mirror the offline atomic
        // rewrite even when the broker call succeeded. Because the broker
        // already updated MO2's in-memory state to the value we are writing,
        // the file and the broker stay in agreement, and MO2's eventual
        // deferred flush is idempotent.
        const text = await readFile(pluginsPath, "utf8");
        const lines = text.split(/\r?\n/).map((l) => {
            const bare = l.replace(/^\*/, "");
            if (bare === args.name)
                return (args.enabled ? "*" : "") + args.name;
            return l;
        });
        await atomicWriteText(pluginsPath, lines.join("\n"));
        if (bound.pipeClient) {
            const result = {
                plugin_state_set: brokerResult,
                plugins_txt_flushed: true,
            };
            if (args.also_hide_file) {
                const espPath = plan.affectedFiles[1];
                const hiddenPath = `${espPath}.mohidden`;
                try {
                    if (args.enabled) {
                        await rename(hiddenPath, espPath);
                    }
                    else {
                        await rename(espPath, hiddenPath);
                    }
                    result.file_renamed = true;
                }
                catch (e) {
                    result.file_rename_failed = e instanceof Error ? e.message : String(e);
                }
                await bound.pipeClient.call("organizer.refresh", { save_changes: false }).catch(() => { });
            }
            result.pluginWarnings = await pollPluginWarnings(bound.pipeClient);
            await logApplyEvent(handler.toolName, `${args.enabled ? "enabled" : "disabled"} plugin "${args.name}"`, bound, plan.planId, profile);
            return result;
        }
        // Offline: plugins.txt rewrite already done above; no broker -> no
        // file-hide path.
        await logApplyEvent(handler.toolName, `${args.enabled ? "enabled" : "disabled"} plugin "${args.name}"`, bound, plan.planId, profile);
        return {
            name: args.name,
            enabled: args.enabled,
            source: "offline_plugins_txt_rewrite",
            also_hide_file: args.also_hide_file ? "requires_live_mo2" : false,
        };
    },
};
registerTool({
    name: "mo2_toggle_plugin",
    tier: "T3",
    description: "Enable/disable plugin. Optional also_hide_file=true renames the .esp to .mohidden for Optional-ESP semantics (live-mode only).",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
