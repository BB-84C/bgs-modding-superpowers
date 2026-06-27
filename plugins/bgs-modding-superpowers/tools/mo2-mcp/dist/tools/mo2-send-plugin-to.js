/**
 * mo2_send_plugin_to — T3 reposition a plugin by GUI-aligned target mode.
 *
 * Two priority spaces:
 *
 * - LIVE (broker present): mobase `IPluginList::setPriority` operates in the
 *   FULL plugin-priority space, which interleaves foreign-managed officials
 *   (e.g., Starfield's 12 official masters at priorities 0..11) with the user-
 *   controllable plugins. The broker is authoritative; this tool queries
 *   `plugins.list` and computes targets against the real mobase priorities.
 *   To keep the user-facing semantics intuitive, the target search is filtered
 *   to plugins.txt entries (foreign officials are not addressable as anchors
 *   and do not pin `gui_top`/`gui_bottom`).
 *
 * - OFFLINE (no broker): the tool rewrites plugins.txt directly. Priority is
 *   the 0-based forward-index within plugins.txt (after the comment header).
 *
 * Vocabulary contract (mirrors MO2 GUI plugins panel — BOTTOM wins):
 *   - gui_top              → priority of the FIRST plugins.txt entry (loaded first, loses all)
 *   - gui_bottom           → priority of the LAST plugins.txt entry (loaded last, wins all)
 *   - wins_over <anchor>   → anchor.priority + 1
 *   - loses_to <anchor>    → anchor.priority - 1
 *   - raw_priority         → explicit mobase priority (live) / plugins.txt index (offline), clamped
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
const RESPONSE_META_BROKER = {
    priority_convention: "mobase_full_space_higher_wins",
    plugins_txt_file_order: "forward_matches_gui",
    gui_direction_hint: "priority is mobase IPluginList space; foreign officials occupy a leading prefix; higher_priority_wins",
    priority_space: "mobase",
};
const RESPONSE_META_OFFLINE = {
    priority_convention: "plugins_txt_forward_space_higher_wins",
    plugins_txt_file_order: "forward_matches_gui",
    gui_direction_hint: "priority_0_at_gui_top_loads_first_loses; priority_(N-1)_at_gui_bottom_loads_last_wins",
    priority_space: "plugins_txt_index",
};
/**
 * LIVE-mode priority view. Filters broker's full plugin list down to the
 * plugins.txt entries (foreign officials excluded) so user-facing min/max
 * and anchor lookups match what the curator sees in the GUI panel.
 */
async function _pluginPrioritiesFromBroker(ctx, profile) {
    const bound = requireBoundContext(ctx);
    if (!bound.pipeClient)
        throw new Error("broker_required_for_live_priority_view");
    const resp = await bound.pipeClient.call("plugins.list", {});
    if (!resp.ok)
        throw new Error(resp.error?.message ?? "plugins.list failed");
    const result = resp.result ?? {};
    const list = result.plugins ?? [];
    const profileData = await readProfile(join(bound.config.mo2Root, "profiles", profile));
    const inPluginsTxt = new Set(profileData.plugins.filter((p) => !p.isComment).map((p) => p.name));
    return list
        .filter((p) => inPluginsTxt.has(p.name))
        .filter((p) => typeof p.priority === "number")
        .map((p) => ({ name: p.name, priority: p.priority }));
}
/**
 * OFFLINE-mode priority view. Assigns sequential 0-based indices over the
 * plugins.txt entries (after the comment header).
 */
async function _pluginPrioritiesFromFile(ctx, profile) {
    const bound = requireBoundContext(ctx);
    const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
    return p.plugins
        .filter((plugin) => !plugin.isComment)
        .map((plugin, priority) => ({ name: plugin.name, priority }));
}
async function _computeTargetPriority(args, ctx, profile) {
    const bound = requireBoundContext(ctx);
    const useBroker = !!bound.pipeClient;
    const plugins = useBroker
        ? await _pluginPrioritiesFromBroker(ctx, profile)
        : await _pluginPrioritiesFromFile(ctx, profile);
    if (plugins.length === 0) {
        throw new Error("no_plugins_in_profile");
    }
    const priorities = plugins.map((p) => p.priority);
    const maxPri = Math.max(...priorities);
    const minPri = Math.min(...priorities);
    const clamp = (v) => Math.max(0, Math.min(v, maxPri));
    const source = plugins.find((p) => p.name === args.name);
    if (!source)
        throw new Error(`plugin_not_found: ${String(args.name)}`);
    const mode = args.target_mode;
    switch (mode) {
        case "gui_top":
            return { priority: minPri, useBroker };
        case "gui_bottom":
            return { priority: maxPri, useBroker };
        case "raw_priority": {
            const tp = args.target_priority;
            if (typeof tp !== "number" || !Number.isInteger(tp)) {
                throw new Error("raw_priority_requires_target_priority_int");
            }
            return { priority: clamp(tp), useBroker };
        }
        case "wins_over":
        case "loses_to": {
            const anchorName = args.anchor;
            if (typeof anchorName !== "string" || anchorName.length === 0) {
                throw new Error(`${mode}_requires_anchor`);
            }
            const anchor = plugins.find((p) => p.name === anchorName);
            if (!anchor)
                throw new Error(`anchor_not_found: ${anchorName}`);
            return {
                priority: clamp(mode === "wins_over" ? anchor.priority + 1 : anchor.priority - 1),
                useBroker,
            };
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
        const { priority: targetPri, useBroker } = await _computeTargetPriority(args, ctx, profile);
        const pluginsPath = join(resolveProfileDir(ctx, profile), "plugins.txt");
        const space = useBroker ? "mobase" : "plugins_txt_index";
        const diffMeta = (() => {
            switch (args.target_mode) {
                case "gui_top": return `gui_top (priority ${targetPri} = loads first = loses all)`;
                case "gui_bottom": return `gui_bottom (priority ${targetPri} = loads last = wins all)`;
                case "wins_over": return `wins_over ${args.anchor}`;
                case "loses_to": return `loses_to ${args.anchor}`;
                case "raw_priority": return `raw_priority ${args.target_priority}`;
                default: return String(args.target_mode);
            }
        })();
        return {
            diff: `${args.name}: → priority ${targetPri} [${space}] (${diffMeta})`,
            affectedFiles: [pluginsPath],
            targets: [{ path: pluginsPath, kind: "text-file" }],
        };
    },
    async applyMutation(plan, ctx) {
        const bound = requireBoundContext(ctx);
        const args = plan.args;
        const profile = args.profile ?? "Default";
        const { priority: targetPri, useBroker } = await _computeTargetPriority(args, ctx, profile);
        if (bound.pipeClient && useBroker) {
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
                _meta: RESPONSE_META_BROKER,
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
            _meta: RESPONSE_META_OFFLINE,
        };
    },
};
registerTool({
    name: "mo2_send_plugin_to",
    tier: "T3",
    description: "Reposition a plugin in plugins.txt by GUI-aligned target mode. Live: broker plugins.set_priority in mobase priority space. Offline: plugins.txt rewrite in forward-index space. Vocabulary matches mo2_send_mod_to; see _meta in response for direction and space contract.",
    inputSchema,
    handler: (args, ctx) => routeToPlanApply(handler, args, ctx, ctx.plans, ctx.snapshots),
});
