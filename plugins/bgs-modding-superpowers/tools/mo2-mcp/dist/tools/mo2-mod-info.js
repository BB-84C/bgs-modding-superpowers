/**
 * mo2_mod_info — T1 single mod detail.
 *
 * Returns: name, absolute_path, meta.ini parsed sections, file count, archive count.
 */
import { z } from "zod";
import { join } from "node:path";
import { readFile, readdir, stat } from "node:fs/promises";
import { registerTool } from "../tool-registry.js";
import { readMoIni } from "../mo-ini.js";
import { requireBoundContext } from "../binding.js";
const inputSchema = z.object({
    name: z.string(),
});
function parseMetaIni(text) {
    const sections = {};
    let current = "";
    for (const line of text.split(/\r?\n/)) {
        const m = line.match(/^\[(.+)\]$/);
        if (m) {
            current = m[1];
            sections[current] = sections[current] ?? {};
            continue;
        }
        if (!current)
            continue;
        const eq = line.indexOf("=");
        if (eq > 0)
            sections[current][line.slice(0, eq).trim()] = line.slice(eq + 1);
    }
    return sections;
}
registerTool({
    name: "mo2_mod_info",
    tier: "T1",
    description: "Single mod detail: meta.ini parsed sections, file count, archive count (BA2/BSA), absolute path.",
    inputSchema,
    handler: async (args, ctx) => {
        const bound = requireBoundContext(ctx);
        const name = args.name;
        const ini = await readMoIni(join(bound.config.mo2Root, "ModOrganizer.ini"));
        const modsDir = ini.settings.modDirectory ?? join(bound.config.mo2Root, "mods");
        const modPath = join(modsDir, name);
        try {
            await stat(modPath);
        }
        catch {
            return { ok: false, error: { code: "mod_not_found", message: name } };
        }
        let meta = {};
        try {
            const metaText = await readFile(join(modPath, "meta.ini"), "utf8");
            meta = parseMetaIni(metaText);
        }
        catch {
            // no meta.ini
        }
        let fileCount = 0;
        let archiveCount = 0;
        async function walk(d) {
            const entries = await readdir(d, { withFileTypes: true }).catch(() => []);
            for (const e of entries) {
                const full = join(d, e.name);
                if (e.isDirectory()) {
                    await walk(full);
                }
                else {
                    fileCount++;
                    if (/\.(ba2|bsa)$/i.test(e.name))
                        archiveCount++;
                }
            }
        }
        await walk(modPath);
        return {
            ok: true,
            result: {
                name,
                absolute_path: modPath,
                meta,
                file_count: fileCount,
                archive_count: archiveCount,
            },
            error: null,
        };
    },
});
