/**
 * ModOrganizer.ini parser.
 *
 * Handles Qt QSettings INI array dialect for [customExecutables]:
 *   size=2
 *   1\title=xEdit
 *   1\binary=...
 *   2\title=LOOT
 *
 * Preserves other sections verbatim via sectionRanges so future writes
 * (e.g., mo2_configure_executable in S4) can replace [customExecutables]
 * without touching anything else.
 */
import { readFile } from "node:fs/promises";
const BOOL_KEYS = new Set(["ownicon", "hide", "toolbar", "minimizeToSystemTray"]);
function decodeIniValue(value) {
    const byteArray = value.match(/^@ByteArray\((.*)\)$/);
    if (!byteArray)
        return value;
    return byteArray[1].replace(/\\\\/g, "\\");
}
export async function readMoIni(path) {
    const raw = await readFile(path, "utf8");
    const lines = raw.split(/\r?\n/);
    const sectionRanges = new Map();
    const sectionLines = new Map();
    let currentSection = "";
    let sectionStart = 0;
    for (let i = 0; i < lines.length; i++) {
        const match = lines[i].trim().match(/^\[(.+)\]$/);
        if (match) {
            if (currentSection)
                sectionRanges.set(currentSection, [sectionStart, i - 1]);
            currentSection = match[1];
            sectionStart = i;
            sectionLines.set(currentSection, []);
        }
        else if (currentSection) {
            sectionLines.get(currentSection).push(lines[i]);
        }
    }
    if (currentSection)
        sectionRanges.set(currentSection, [sectionStart, lines.length - 1]);
    const parseFlat = (sectionName) => {
        const result = {};
        for (const line of sectionLines.get(sectionName) ?? []) {
            const eq = line.indexOf("=");
            if (eq > 0)
                result[line.slice(0, eq).trim()] = decodeIniValue(line.slice(eq + 1));
        }
        return result;
    };
    const general = parseFlat("General");
    const settings = parseFlat("Settings");
    const customExecutables = [];
    const customFlat = parseFlat("customExecutables");
    const size = Number.parseInt(customFlat.size ?? "0", 10);
    const entryCount = Number.isFinite(size) ? size : 0;
    for (let i = 1; i <= entryCount; i++) {
        const entry = {};
        for (const [key, value] of Object.entries(customFlat)) {
            const parts = key.split("\\");
            if (parts.length !== 2 || parts[0] !== String(i))
                continue;
            const subKey = parts[1];
            if (BOOL_KEYS.has(subKey)) {
                entry[subKey] = value.trim().toLowerCase() === "true";
            }
            else {
                entry[subKey] = value;
            }
        }
        if (typeof entry.title === "string") {
            customExecutables.push(entry);
        }
    }
    return {
        raw,
        general: {
            game: general.game,
            gameName: general.gameName,
            gamePath: general.gamePath,
            selectedProfile: general.selected_profile,
        },
        settings: {
            baseDirectory: settings.base_directory,
            modDirectory: settings.mod_directory,
            downloadDirectory: settings.download_directory,
            profilesDirectory: settings.profiles_directory,
            overwriteDirectory: settings.overwrite_directory,
            cacheDirectory: settings.cache_directory,
        },
        customExecutables,
        sectionRanges,
    };
}
