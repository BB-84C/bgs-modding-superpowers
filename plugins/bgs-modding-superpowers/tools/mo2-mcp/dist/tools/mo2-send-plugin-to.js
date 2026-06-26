/**
 * mo2_send_plugin_to — T3 reposition a plugin by GUI-aligned target mode.
 *
 * plugins.txt is FORWARD order and matches the MO2 GUI plugins pane:
 *   - gui_top              → priority 0 (loaded first, loses all plugin conflicts)
 *   - gui_bottom           → priority N-1 (loaded last, wins all plugin conflicts)
 *   - wins_over <anchor>   → anchor.priority + 1
 *   - loses_to <anchor>    → anchor.priority - 1
 *   - raw_priority         → explicit plugins.txt priority, clamped [0, N-1]
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
const ModeSchema = z.enum([
    "gui_top",
    "gui_bottom",
    "wins_over",
    "loses_to",
    "raw_priority",
]);
const inputSchema = z.discriminatedUnion("mode", [
    z.object({
        mode: z.literal("plan"),
        name: z.string().min(1),
        target_mode: ModeSchema,
        anchor: z.string().min(1).optional(),
        target_priority: z.number().int().optional(),
        profile: z.string().default("Default"),
    }).strict(),
    z.object({ mode: z.literal("apply"), plan_id: z.string().min(1), lease_token: z.string().min(1) }).strict(),
]);
const RESPONSE_META = {
    priority_convention: "plugins_txt_forward_space_higher_wins",
    plugins_txt_file_order: "forward_matches_gui",
    gui_direction_hint: "priority_0_at_gui_top_loads_first_loses; priority_(N-1)_at_gui_bottom_loads_last_wins",
};
async function _pluginPriorities(ctx, profile) {
    const bound = requireBoundContext(ctx);
    const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
    return p.plugins
        .filter((plugin) => !plugin.isComment)
        .map((plugin, priority) => ({ name: plugin.name, priority }));
}
async function _computeTargetPriority(args, ctx, profile) {
    const plugins = await _pluginPriorities(ctx, profile);
    const maxPri = Math.max(0, plugins.length - 1);
    const clamp = (v) => Math.max(0, Math.min(v, maxPri));
    const source = plugins.find((plugin) => plugin.name === args.name);
    if (!source)
        throw new Error(`plugin_not_found: ${String(args.name)}`);
    const mode = args.target_mode;
    switch (mode) {
        case "gui_top":
            return 0;
        case "gui_bottom":
            return maxPri;
        case "raw_priority": {
            const tp = args.target_priority;
            if (typeof tp !== "number" || !Number.isInteger(tp)) {
                throw new Error("raw_priority_requires_target_priority_int");
            }
            return clamp(tp);
        }
        case "wins_over":
        case "loses_to": {
            const anchorName = args.anchor;
            if (typeof anchorName !== "string" || anchorName.length === 0) {
                throw new Error(`${mode}_requires_anchor`);
            }
            const anchor = plugins.find((plugin) => plugin.name === anchorName);
            if (!anchor)
                throw new Error(`anchor_not_found: ${anchorName}`);
            return clamp(mode === "wins_over" ? anchor.priority + 1 : anchor.priority - 1);
        }
        default:
            throw new Error(`unknown_mode: ${mode}`);
    }
}
function _rewritePluginsTxtAtPriority(text, pluginName, targetPriority) {
    const rawLines = text.split(/\r?\n/).filter((line) => line.length > 0);
    const commentLines = rawLines.filter((line) => line.startsWith("#"));
    const pluginLines = rawLines
        .filter((line) => !line.startsWith("#"))
        .filter((line) => line.replace(/^\*/, "").trim() !== pluginName);
    const sourceLine = rawLines.find((line) => !line.startsWith("#") && line.replace(/^\*/, "").trim() === pluginName)
        ?? `*${pluginName}`;
    const insertIdx = Math.max(0, Math.min(targetPriority, pluginLines.length));
    pluginLines.splice(insertIdx, 0, sourceLine);
    return `${[...commentLines, ...pluginLines].join("\n")}\n`;
}
const handler = {
    toolName: "mo2_send_plugin_to",
    async buildPlan(args, ctx) {
        const profile = args.profile ?? "Default";
        await assertActiveProfile(ctx, profile);
        const targetPri = await _computeTargetPriority(args, ctx, profile);
        const pluginsPath = join(resolveProfileDir(ctx, profile), "plugins.txt");
        const p = await _pluginPriorities(ctx, profile);
        const maxPri = Math.max(0, p.length - 1);
        const diffMeta = (() => {
            switch (args.target_mode) {
                case "gui_top": return "gui_top (priority 0 = loads first = loses all)";
                case "gui_bottom": return `gui_bottom (priority ${maxPri} = loads last = wins all)`;
                case "wins_over": return `wins_over ${args.anchor}`;
                case "loses_to": return `loses_to ${args.anchor}`;
                case "raw_priority": return `raw_priority ${args.target_priority}`;
                default: return String(args.target_mode);
            }
        })();
        return {
            diff: `${args.name}: → priority ${targetPri} (${diffMeta})`,
            affectedFiles: [pluginsPath],
            targets: [{ path: pluginsPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const profile = args.profile ?? "Default";
        const targetPri = await _computeTargetPriority(args, ctx, profile);
        if (bound.pipeClient) {
            await assertActiveProfile(ctx, profile);
            const resp = await bound.pipeClient.call("plugins.set_priority", {
                name: args.name,
                priority: targetPri,
            });
            if (!resp.ok)
                throw new Error(resp.error?.message ?? "plugins.set_priority failed");
            return {
                ...resp.result,
                new_priority: targetPri,
                target_mode: args.target_mode,
                _meta: RESPONSE_META,
            };
        }
        const pluginsPath = join(resolveProfileDir(ctx, profile), "plugins.txt");
        const text = await readFile(pluginsPath, "utf8");
        await atomicWriteText(pluginsPath, _rewritePluginsTxtAtPriority(text, args.name, targetPri));
        return {
            name: args.name,
            new_priority: targetPri,
            target_mode: args.target_mode,
            source: "offline_plugins_txt_reorder",
            _meta: RESPONSE_META,
        };
    },
};
registerTool({
    name: "mo2_send_plugin_to",
    tier: "T3",
    description: "Reposition a plugin in plugins.txt by GUI-aligned target mode. Live: broker plugins.set_priority. Offline: plugins.txt rewrite. Vocabulary matches mo2_send_mod_to; see _meta in response for direction contract.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
