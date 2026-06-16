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
        return {
            ok: true,
            result: { profile, mods, mod_count: mods.length },
            error: null,
        };
    },
});
