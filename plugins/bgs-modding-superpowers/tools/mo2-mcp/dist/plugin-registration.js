import { readFile, readdir } from "node:fs/promises";
import { extname } from "node:path";
import { atomicWriteText } from "./atomic.js";
const PLUGIN_EXTS = new Set([".esm", ".esp", ".esl"]);
// Enumerate plugin files at an MO2 mod root and register newly discovered
// entries in plugins.txt enabled (`*` prefix). Existing entries are preserved
// case-insensitively so a disabled user choice is never overwritten.
export async function registerPluginsInPluginsTxt(modRoot, pluginsTxtPath) {
    let modEntries;
    try {
        modEntries = await readdir(modRoot, { withFileTypes: true });
    }
    catch {
        return [];
    }
    const newPlugins = modEntries
        .filter((e) => e.isFile() && PLUGIN_EXTS.has(extname(e.name).toLowerCase()))
        .map((e) => e.name)
        .sort();
    if (newPlugins.length === 0)
        return [];
    const existingTxt = await readFile(pluginsTxtPath, "utf8").catch(() => "");
    const existingLower = new Set(existingTxt
        .split(/\r?\n/)
        .filter((line) => line.length > 0 && !line.startsWith("#"))
        .map((line) => line.replace(/^\*/, "").trim().toLowerCase()));
    const linesToAdd = [];
    const registered = [];
    for (const plugin of newPlugins) {
        if (!existingLower.has(plugin.toLowerCase())) {
            linesToAdd.push(`*${plugin}`);
            registered.push(plugin);
        }
    }
    if (linesToAdd.length === 0)
        return [];
    const sep = existingTxt.length === 0 || existingTxt.endsWith("\n") ? "" : "\n";
    const newTxt = `${existingTxt}${sep}${linesToAdd.join("\n")}\n`;
    await atomicWriteText(pluginsTxtPath, newTxt);
    return registered;
}
