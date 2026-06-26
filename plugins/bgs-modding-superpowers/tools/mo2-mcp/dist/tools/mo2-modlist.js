/**
 * mo2_modlist — T1 native TS read of modlist.txt.
 *
 * Returns mods with name + priority + enabled + is_separator (offline-fast).
 * Optional enrich=true: when broker pipe is live, adds live_priority from
 * mobase IModList for cross-check.
 */
import { z } from "zod";
import { join } from "node:path";
import { registerTool } from "../tool-registry.js";
import { readProfile } from "../profile-reader.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.object({
    profile: z.string().default("Default"),
    enrich: z.boolean().default(false),
});
function effectivePriority(mod) {
    return typeof mod.live_priority === "number" ? mod.live_priority : mod.priority;
}
function enrichGuiFields(mods) {
    const separators = mods
        .filter((m) => m.is_separator)
        .map((m) => ({ name: m.name, priority: effectivePriority(m) }))
        .sort((a, b) => b.priority - a.priority);
    return mods
        .map((m) => {
        const priority = effectivePriority(m);
        const section = m.is_separator ? null : (separators.find((s) => s.priority < priority)?.name ?? null);
        return {
            ...m,
            section,
            gui_rank: priority + 1,
            wins_over_count: priority,
        };
    })
        .sort((a, b) => effectivePriority(a) - effectivePriority(b));
}
registerTool({
    name: "mo2_modlist",
    tier: "T1",
    description: "Read modlist.txt. Returns mods with name/priority/enabled/is_separator. Native TS read (offline-fast). If enrich=true and MO2 is live, adds live_priority via broker.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        const profile = args.profile ?? "Default";
        const profileDir = join(bound.config.mo2Root, "profiles", profile);
        const p = await readProfile(profileDir);
        let mods = p.mods.map((m) => ({
            name: m.name,
            priority: m.priority,
            enabled: m.enabled,
            is_separator: m.isSeparator,
        }));
        if (args.enrich && bound.pipeClient) {
            try {
                const resp = await bound.pipeClient.call("mods.list", {});
                if (resp.ok && resp.result && typeof resp.result === "object") {
                    const liveMods = resp.result.mods ?? [];
                    const liveMap = new Map(liveMods.map((m) => [m.name, m]));
                    mods = mods.map((m) => ({
                        ...m,
                        live_priority: liveMap.get(m.name)?.priority ?? null,
                    }));
                }
            }
            catch {
                // Pipe failure → skip enrich silently
            }
        }
        const guiMods = enrichGuiFields(mods);
        return {
            ok: true,
            result: {
                profile,
                mods: guiMods,
                mod_count: p.mods.length,
                _meta: {
                    array_order: "gui_top_first",
                    array_order_note: "First entry is at TOP of MO2 GUI mods panel (lowest priority = loses all conflicts). Last entry is at BOTTOM of GUI (highest priority = wins all conflicts).",
                    priority_convention: "mobase_full_space_higher_wins",
                    section_rule: "A separator at priority X labels mods at priorities X+1..(next_higher_separator.priority - 1). Each mod's 'section' field is the name of the separator that labels it (null if no separator below it in priority).",
                },
            },
            error: null,
        };
    },
});
