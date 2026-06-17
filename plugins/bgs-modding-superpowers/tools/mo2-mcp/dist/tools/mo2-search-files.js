/**
 * mo2_search_files — T1 glob/regex file search across enabled mods.
 *
 * Bounded by max_results. Pattern: glob like "**\/*.esp" or regex with
 * "regex:" prefix. Walks each enabled mod's directory; returns relative
 * paths prefixed by mod name.
 */
import { z } from "zod";
import { join } from "node:path";
import { readdir } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { readProfile } from "../profile-reader.js";
import { requireBoundContext } from "../binding.js";
// BUG-10 fix (2026-06-17): pattern gains .min(1). Empty glob/regex would match
// nothing useful and falls through silently today; explicit invalid_arguments
// is the correct contract.
const inputSchema = z.object({
    profile: z.string().default("Default"),
    pattern: z.string().min(1),
    max_results: z.number().int().min(1).max(10000).default(1000),
});
function globToRegex(pattern) {
    // Escape regex metachars (but NOT *, ?, /).
    const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    // Consume `**` together with an optional trailing `/` so the slash
    // collapses when `**` matches zero segments. This is the standard glob
    // semantic used by minimatch / picomatch / fast-glob: `**/*.esp` matches
    // both `dir/foo.esp` and root-level `foo.esp`.
    const transformed = escaped
        .replace(/\*\*\/?/g, "\x01")
        .replace(/\*/g, "[^/]*")
        .replace(/\?/g, "[^/]")
        .replace(/\x01/g, "(?:.*/)?");
    return new RegExp(`^${transformed}$`, "i");
}
function _stripDataPrefixFromPattern(pattern) {
    if (pattern.startsWith("regex:")) {
        const source = pattern.slice("regex:".length);
        const stripped = source.replace(/^(\^?)(?:\[(?:Dd|dD)\]ata|data)\//i, "$1");
        return "regex:" + stripped;
    }
    return pattern.replace(/^data\//i, "");
}
registerTool({
    name: "mo2_search_files",
    tier: "T1",
    description: "Glob/regex file search across enabled mod trees. Bounded by max_results (default 1000). pattern='**/*.esp' for glob, 'regex:^foo' for regex. Returns mod-prefixed paths + truncated flag.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        const profile = args.profile ?? "Default";
        const inputPattern = args.pattern;
        const pattern = _stripDataPrefixFromPattern(inputPattern);
        const maxResults = args.max_results ?? 1000;
        const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
        const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
        const p = await readProfile(join(bound.config.mo2Root, "profiles", profile));
        const enabled = p.mods.filter((m) => m.enabled && !m.isSeparator);
        const isRegex = pattern.startsWith("regex:");
        const matcher = isRegex ? new RegExp(pattern.slice(6), "i") : globToRegex(pattern);
        const results = [];
        let truncated = false;
        outer: for (const mod of enabled) {
            const root = join(modsDir, mod.name);
            const walk = async (dir) => {
                if (results.length >= maxResults) {
                    truncated = true;
                    return;
                }
                const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
                for (const e of entries) {
                    if (results.length >= maxResults) {
                        truncated = true;
                        return;
                    }
                    const full = join(dir, e.name);
                    if (e.isDirectory()) {
                        await walk(full);
                    }
                    else {
                        const rel = full.slice(root.length + 1).replace(/\\/g, "/");
                        if (matcher.test(rel))
                            results.push(`${mod.name}/${rel}`);
                    }
                }
            };
            await walk(root);
            if (truncated)
                break outer;
        }
        return {
            ok: true,
            result: { results, truncated, count: results.length, pattern: inputPattern, profile },
            error: null,
        };
    },
});
